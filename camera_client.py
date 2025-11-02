#!/usr/bin/env python3
"""
Compatible TCP/IP Client for pyLabLib Camera Control Server

This client can communicate with the server.py plugin to:
- Control camera acquisition
- Get/set GUI parameters
- Control frame saving
- Stream frame data
- Get camera parameters

Usage example:
    client = CameraControlClient('localhost', 18923)
    client.connect()
    client.start_acquisition()
    frames = client.get_frames(10)
    client.stop_acquisition()
    client.disconnect()
"""

import socket
import json
import numpy as np
import time
from typing import Dict, Any, Tuple


class ClientError(Exception):
    """Client communication error"""

    def __init__(self, message, error_data=None):
        super().__init__(message)
        self.error_data = error_data


class CameraControlClient:
    """
    TCP/IP Client for pyLabLib Camera Control Server

    Compatible with the server.py plugin protocol.
    """

    def __init__(self, host: str = "localhost", port: int = 18923, timeout: float = 10.0):
        """
        Initialize client

        Args:
            host: Server hostname or IP address
            port: Server port number
            timeout: Socket timeout in seconds
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.socket = None
        self.connected = False
        self._message_id = 0

    def connect(self) -> None:
        """Connect to the server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.host, self.port))

            # Protocol handshake
            handshake = {"protocol": "1.0"}
            self._send_raw_message(handshake)
            response = self._recv_raw_message()

            if response.get("protocol") != "1.0":
                raise ClientError("Protocol version mismatch")

            self.connected = True
            print(f"Connected to camera server at {self.host}:{self.port}")

        except Exception as e:
            if self.socket:
                self.socket.close()
                self.socket = None
            raise ClientError(f"Failed to connect: {e}")

    def disconnect(self) -> None:
        """Disconnect from the server"""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            finally:
                self.socket = None
                self.connected = False
                print("Disconnected from camera server")

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()

    def _get_next_id(self) -> int:
        """Get next message ID"""
        self._message_id += 1
        return self._message_id

    def _send_raw_message(self, msg: Dict) -> None:
        """Send raw message to server"""
        if not self.connected:
            raise ClientError("Not connected to server")

        # Handle numpy array payload
        payload = None
        if "payload" in msg:
            payload = msg["payload"]
            msg["payload"] = {"shape": list(payload.shape), "dtype": payload.dtype.str, "nbytes": payload.nbytes}

        # Send JSON message with length prefix
        json_data = json.dumps(msg).encode("utf-8")
        length = len(json_data)
        self.socket.sendall(length.to_bytes(4, "big") + json_data)

        # Send payload if present
        if payload is not None:
            self.socket.sendall(payload.tobytes())

    def _recv_raw_message(self) -> Dict:
        """Receive raw message from server"""
        if not self.connected:
            raise ClientError("Not connected to server")

        # Receive message length
        length_data = self._recv_exactly(4)
        length = int.from_bytes(length_data, "big")

        # Receive JSON message
        json_data = self._recv_exactly(length)
        msg = json.loads(json_data.decode("utf-8"))

        # Receive payload if specified
        if "payload" in msg and isinstance(msg["payload"], dict):
            payload_info = msg["payload"]
            shape = payload_info["shape"]
            dtype = payload_info["dtype"]
            nbytes = payload_info["nbytes"]

            payload_data = self._recv_exactly(nbytes)
            payload = np.frombuffer(payload_data, dtype=dtype).reshape(shape)
            msg["payload"] = payload

        return msg

    def _recv_exactly(self, nbytes: int) -> bytes:
        """Receive exactly nbytes from socket"""
        data = b""
        while len(data) < nbytes:
            chunk = self.socket.recv(nbytes - len(data))
            if not chunk:
                raise ClientError("Connection closed unexpectedly")
            data += chunk
        return data

    def _send_request(self, name: str, args: Dict = None) -> Any:
        """Send request and return response"""
        if args is None:
            args = {}

        message = {"id": self._get_next_id(), "purpose": "request", "parameters": {"name": name, "args": args}}

        # Handle payload
        if "payload" in args:
            message["payload"] = args.pop("payload")

        self._send_raw_message(message)
        response = self._recv_raw_message()

        if response.get("purpose") == "error":
            error_info = response.get("parameters", {})
            raise ClientError(f"Server error: {error_info.get('name', 'unknown')}", error_info)

        if response.get("purpose") != "reply":
            raise ClientError("Unexpected response type")

        result = response.get("parameters", {})
        if "payload" in response:
            result["payload"] = response["payload"]

        return result

    # Camera Control Methods
    def start_acquisition(self) -> str:
        """Start camera acquisition"""
        return self._send_request("cam/acq/start")

    def stop_acquisition(self) -> str:
        """Stop camera acquisition"""
        return self._send_request("cam/acq/stop")

    def get_camera_parameter(self, param_name: str) -> Any:
        """Get camera parameter value"""
        result = self._send_request("cam/param/get", {"name": param_name})
        return result.get("value")

    def set_camera_parameters(self, params: Dict[str, Any]) -> str:
        """Set camera parameters"""
        return self._send_request("cam/param/set", params)

    # GUI Control Methods
    def get_gui_value(self, name: str) -> Any:
        """Get GUI control value"""
        result = self._send_request("gui/get/value", {"name": name})
        return result.get("value")

    def set_gui_value(self, name: str, value: Any) -> Any:
        """Set GUI control value"""
        result = self._send_request("gui/set/value", {"name": name, "value": value})
        return result.get("value")

    def get_gui_indicator(self, name: str) -> Any:
        """Get GUI indicator value"""
        result = self._send_request("gui/get/indicator", {"name": name})
        return result.get("value")

    def set_gui_indicator(self, name: str, value: Any) -> Any:
        """Set GUI indicator value"""
        result = self._send_request("gui/set/indicator", {"name": name, "value": value})
        return result.get("value")

    # Saving Control Methods
    def start_saving(self, **params) -> str:
        """Start saving frames with optional parameters"""
        return self._send_request("save/start", params)

    def stop_saving(self) -> str:
        """Stop saving frames"""
        return self._send_request("save/stop")

    def snap_frame(self, source: str = None, **params) -> str:
        """Take a snapshot"""
        args = params.copy()
        if source:
            args["source"] = source
        return self._send_request("save/snap", args)

    # Stream Control Methods
    def setup_frame_buffer(self, size: int = 1) -> Dict:
        """Setup frame buffer for streaming"""
        return self._send_request("stream/buffer/setup", {"size": size})

    def clear_frame_buffer(self) -> Dict:
        """Clear frame buffer"""
        return self._send_request("stream/buffer/clear")

    def get_buffer_status(self) -> Dict:
        """Get frame buffer status"""
        return self._send_request("stream/buffer/status")

    def get_frames(self, n: int = None, peek: bool = False) -> Tuple[np.ndarray, int, int]:
        """
        Get frames from buffer

        Args:
            n: Number of frames to read (None = all)
            peek: If True, don't remove frames from buffer

        Returns:
            Tuple of (frames_array, first_index, last_index)
        """
        args = {"peek": peek}
        if n is not None:
            args["n"] = n

        result = self._send_request("stream/buffer/read", args)
        frames = result.get("payload", np.array([]))
        first_idx = result.get("first_index", 0)
        last_idx = result.get("last_index", 0)

        return frames, first_idx, last_idx

    # Convenience Methods
    def acquire_frames(self, n_frames: int = 10, buffer_size: int = None) -> np.ndarray:
        """
        Acquire a specific number of frames

        Args:
            n_frames: Number of frames to acquire
            buffer_size: Buffer size (defaults to n_frames)

        Returns:
            Array of acquired frames
        """
        if buffer_size is None:
            buffer_size = max(n_frames, 10)

        # Setup buffer
        self.setup_frame_buffer(buffer_size)
        self.clear_frame_buffer()

        # Start acquisition
        self.start_acquisition()

        collected_frames = []
        try:
            while len(collected_frames) < n_frames:
                time.sleep(0.1)  # Small delay
                status = self.get_buffer_status()

                if status["filled"] > 0:
                    frames, _, _ = self.get_frames()
                    if len(frames) > 0:
                        # Handle both 3D and 2D frame arrays
                        if frames.ndim == 3:
                            collected_frames.extend(frames)
                        elif frames.ndim == 2:
                            collected_frames.append(frames)

                        if len(collected_frames) >= n_frames:
                            break

        finally:
            self.stop_acquisition()

        # Return exactly n_frames
        return np.array(collected_frames[:n_frames])


def main():
    """Example usage of the client"""
    print("Camera Control Client Example")
    print("=" * 40)

    try:
        # Connect to server
        with CameraControlClient("localhost", 18923) as client:
            print("✓ Connected to server")

            # Get some camera parameters
            try:
                roi = client.get_camera_parameter("roi")
                print(f"✓ Camera ROI: {roi}")
            except ClientError as e:
                print(f"⚠ Could not get ROI: {e}")

            # Setup frame buffer
            status = client.setup_frame_buffer(size=5)
            print(f"✓ Buffer setup: {status}")

            # Acquire some frames
            print("Starting frame acquisition...")
            frames = client.acquire_frames(n_frames=3)
            print(f"✓ Acquired {len(frames)} frames")

            if len(frames) > 0:
                print(f"  Frame shape: {frames[0].shape}")
                print(f"  Frame dtype: {frames[0].dtype}")
                print(f"  Frame range: {frames[0].min()} - {frames[0].max()}")

            # Test GUI interaction (if available)
            try:
                # This will fail if GUI elements don't exist, which is expected
                exposure = client.get_gui_value("exposure")
                print(f"✓ Exposure setting: {exposure}")
            except ClientError:
                print("⚠ GUI controls not available or not accessible")

            print("✓ Client test completed successfully!")

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
