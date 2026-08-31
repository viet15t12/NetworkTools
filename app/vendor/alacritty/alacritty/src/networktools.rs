//! CAMS-managed terminal integration over the local NTTP/1 socket.
//! Added by CAMS to Alacritty upstream baseline
//! 1b2b36a64e88068ad02c95fad00ee2fad31c00bf; see ../../NETWORKTOOLS-CHANGES.md.

use std::io::{BufRead, BufReader, Write};
use std::os::unix::net::UnixStream;
use std::path::PathBuf;
use std::sync::mpsc::{self, Sender};
use std::thread;
use std::time::Duration;

use serde_json::{Value, json};
use winit::event_loop::EventLoopProxy;

use crate::event::{Event, EventType, NttpCommand};

const PROTOCOL: &str = "nttp/1";
const MAX_MESSAGE_BYTES: usize = 64 * 1024;

#[derive(Clone, Debug)]
pub struct ManagedOptions {
    pub session_id: String,
    pub device_id: String,
    pub device_name: String,
    pub host: String,
    pub ipc_path: PathBuf,
}

#[derive(Debug)]
enum Outbound {
    Event(&'static str, Value),
    Stop,
}

/// Handle used by the UI thread to publish lifecycle events.
pub struct NttpClient {
    sender: Sender<Outbound>,
}

impl NttpClient {
    pub fn spawn(options: ManagedOptions, proxy: EventLoopProxy<Event>) -> Self {
        let (sender, receiver) = mpsc::channel();
        thread::Builder::new()
            .name(String::from("networktools-nttp"))
            .spawn(move || {
                let mut stream = match UnixStream::connect(&options.ipc_path) {
                    Ok(stream) => stream,
                    Err(err) => {
                        eprintln!("CAMS Terminal IPC connection failed: {err}");
                        return;
                    },
                };
                let _ = stream.set_read_timeout(Some(Duration::from_millis(100)));
                let reader_stream = match stream.try_clone() {
                    Ok(stream) => stream,
                    Err(err) => {
                        eprintln!("CAMS Terminal IPC initialization failed: {err}");
                        return;
                    },
                };
                let mut reader = BufReader::new(reader_stream);
                let _ = write_event(&mut stream, &options, "terminal.started", json!({
                    "pid": std::process::id(),
                }));

                loop {
                    while let Ok(outbound) = receiver.try_recv() {
                        match outbound {
                            Outbound::Event(event, data) => {
                                if write_event(&mut stream, &options, event, data).is_err() {
                                    return;
                                }
                            },
                            Outbound::Stop => return,
                        }
                    }

                    let mut line = String::new();
                    match reader.read_line(&mut line) {
                        Ok(0) => return,
                        Ok(_) if line.len() <= MAX_MESSAGE_BYTES => {
                            handle_command(&mut stream, &options, &proxy, &line);
                        },
                        Ok(_) => return,
                        Err(err)
                            if matches!(
                                err.kind(),
                                std::io::ErrorKind::WouldBlock | std::io::ErrorKind::TimedOut
                            ) => {},
                        Err(_) => return,
                    }
                }
            })
            .expect("failed to spawn CAMS NTTP thread");
        Self { sender }
    }

    pub fn event(&self, event: &'static str, data: Value) {
        let _ = self.sender.send(Outbound::Event(event, data));
    }

    pub fn close(self) {
        let _ = self.sender.send(Outbound::Event("terminal.closed", json!({})));
        let _ = self.sender.send(Outbound::Stop);
    }
}

fn handle_command(
    stream: &mut UnixStream,
    options: &ManagedOptions,
    proxy: &EventLoopProxy<Event>,
    line: &str,
) {
    let message: Value = match serde_json::from_str(line) {
        Ok(message) => message,
        Err(_) => return,
    };
    if message.get("protocol").and_then(Value::as_str) != Some(PROTOCOL)
        || message.get("type").and_then(Value::as_str) != Some("command")
        || message.get("session_id").and_then(Value::as_str) != Some(options.session_id.as_str())
    {
        return;
    }
    let request_id = match message.get("request_id").and_then(Value::as_str) {
        Some(request_id) if !request_id.is_empty() && request_id.len() <= 128 => request_id,
        _ => return,
    };
    let command_name = message.get("command").and_then(Value::as_str).unwrap_or_default();
    let command = match command_name {
        "window.focus" => Some(NttpCommand::Focus),
        "window.close" => Some(NttpCommand::Close),
        "window.set_title" => message
            .pointer("/data/title")
            .and_then(Value::as_str)
            .filter(|title| {
                !title.is_empty()
                    && title.chars().count() <= 128
                    && !title.chars().any(char::is_control)
            })
            .map(|title| NttpCommand::SetTitle(title.to_owned())),
        "session.ping" => Some(NttpCommand::Ping),
        "session.get_info" => Some(NttpCommand::GetInfo),
        _ => None,
    };
    let ok = command.is_some();
    if let Some(command) = command {
        let _ = proxy.send_event(Event::new(EventType::Nttp(command), None));
    }
    let data = if command_name == "session.get_info" {
        json!({
            "pid": std::process::id(),
            "device_name": options.device_name,
            "host": options.host,
        })
    } else {
        json!({})
    };
    let response = json!({
        "protocol": PROTOCOL,
        "type": "response",
        "session_id": options.session_id,
        "device_id": options.device_id,
        "request_id": request_id,
        "ok": ok,
        "data": data,
    });
    let _ = writeln!(stream, "{response}");
    let _ = stream.flush();
}

fn write_event(
    stream: &mut UnixStream,
    options: &ManagedOptions,
    event: &'static str,
    data: Value,
) -> std::io::Result<()> {
    let message = json!({
        "protocol": PROTOCOL,
        "type": "event",
        "session_id": options.session_id,
        "device_id": options.device_id,
        "event": event,
        "data": data,
    });
    writeln!(stream, "{message}")?;
    stream.flush()
}
