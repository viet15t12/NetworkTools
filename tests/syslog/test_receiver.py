import socket
import threading
import unittest

from features.syslog.models import ListenerConfig
from features.syslog.receiver import SyslogReceiver


class SyslogReceiverTests(unittest.TestCase):
    def test_both_receiver_delivers_udp_and_tcp_on_the_same_port(self) -> None:
        received: list[tuple[bytes, str, str]] = []
        ready = threading.Event()

        def collect(data: bytes, source: str, protocol: str) -> None:
            received.append((data, source, protocol))
            if len(received) == 2:
                ready.set()

        receiver = SyslogReceiver(
            ListenerConfig("127.0.0.1", "127.0.0.1", 0, "both"),
            collect,
            lambda message: None,
        )
        receiver.start()
        try:
            self.assertEqual(len(receiver._servers), 2)
            port = int(receiver._server.getsockname()[1])
            self.assertEqual(
                {int(server.getsockname()[1]) for server in receiver._servers},
                {port},
            )
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_client:
                udp_client.sendto(b"<189>%SYS-5-CONFIG_I: udp", ("127.0.0.1", port))
            with socket.create_connection(("127.0.0.1", port), timeout=2.0) as tcp_client:
                tcp_client.sendall(b"<189>%SYS-5-CONFIG_I: tcp\n")

            self.assertTrue(ready.wait(2.0))
            self.assertEqual({item[2] for item in received}, {"udp", "tcp"})
        finally:
            receiver.stop()

    def test_udp_receiver_delivers_datagram(self) -> None:
        received: list[tuple[bytes, str, str]] = []
        ready = threading.Event()
        receiver = SyslogReceiver(
            ListenerConfig("127.0.0.1", "127.0.0.1", 0, "udp"),
            lambda data, source, protocol: (
                received.append((data, source, protocol)),
                ready.set(),
            ),
            lambda message: None,
        )
        receiver.start()
        try:
            self.assertIsNotNone(receiver._server)
            port = int(receiver._server.getsockname()[1])
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                client.sendto(
                    b"<189>%SYS-5-CONFIG_I: receiver test",
                    ("127.0.0.1", port),
                )
            self.assertTrue(ready.wait(2.0))
            self.assertTrue(received[0][0].endswith(b"receiver test"))
            self.assertEqual(received[0][2], "udp")
        finally:
            receiver.stop()

    def test_tcp_receiver_delivers_final_frame_without_newline(self) -> None:
        received: list[tuple[bytes, str, str]] = []
        ready = threading.Event()
        receiver = SyslogReceiver(
            ListenerConfig("127.0.0.1", "127.0.0.1", 0, "tcp"),
            lambda data, source, protocol: (
                received.append((data, source, protocol)),
                ready.set(),
            ),
            lambda message: None,
        )
        receiver.start()
        try:
            self.assertIsNotNone(receiver._server)
            port = int(receiver._server.getsockname()[1])
            with socket.create_connection(("127.0.0.1", port), timeout=2.0) as client:
                client.sendall(b"<189>%SYS-5-CONFIG_I: final tcp frame")
            self.assertTrue(ready.wait(2.0))
            self.assertTrue(received[0][0].endswith(b"final tcp frame"))
            self.assertEqual(received[0][2], "tcp")
        finally:
            receiver.stop()


if __name__ == "__main__":
    unittest.main()
