import os
import asyncio
import logging
from typing import Optional, AsyncGenerator

logger = logging.getLogger("tailer")

class FileTailer:
    """
    Async log file tailer that survives log rotation and truncation.
    Yields newly appended lines via an internal bounded queue.
    """
    def __init__(
        self,
        filepath: str,
        poll_interval_sec: float = 0.2,
        from_start: bool = False,
        queue_size: int = 10000
    ):
        self.filepath = os.path.abspath(filepath)
        self.poll_interval_sec = poll_interval_sec
        self.from_start = from_start
        self.queue: asyncio.Queue[str] = asyncio.Queue(maxsize=queue_size)
        
        self.is_running = False
        self._file_obj = None
        self._worker_task: Optional[asyncio.Task] = None
        self._last_inode = None
        self._last_offset = 0
        self.dropped_lines = 0
        self.total_lines_read = 0

    async def start(self):
        if not self.is_running:
            self.is_running = True
            self._worker_task = asyncio.create_task(self._tail_loop())
            logger.info(f"FileTailer started monitoring {self.filepath}")

    async def stop(self):
        self.is_running = False
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        if self._file_obj:
            try:
                self._file_obj.close()
                self._file_obj = None
            except Exception:
                pass
        logger.info("FileTailer stopped.")

    async def get_line(self) -> str:
        return await self.queue.get()

    def _get_stat(self):
        try:
            return os.stat(self.filepath)
        except (FileNotFoundError, OSError):
            return None

    async def _tail_loop(self):
        self._file_obj = None
        partial_line_buffer = ""

        while self.is_running:
            try:
                if not os.path.exists(self.filepath):
                    if self._file_obj:
                        self._file_obj.close()
                        self._file_obj = None
                        partial_line_buffer = ""
                    await asyncio.sleep(self.poll_interval_sec)
                    continue

                stat = self._get_stat()
                if not stat:
                    await asyncio.sleep(self.poll_interval_sec)
                    continue

                # Initial open or reopen on rotation
                current_inode = (stat.st_ino, stat.st_dev)
                if self._file_obj is None:
                    try:
                        self._file_obj = open(self.filepath, "r", encoding="utf-8", errors="replace")
                        if self.from_start:
                            self._last_offset = 0
                            self._file_obj.seek(0, os.SEEK_SET)
                        else:
                            self._file_obj.seek(0, os.SEEK_END)
                            self._last_offset = self._file_obj.tell()
                        self._last_inode = current_inode
                        logger.info(f"Opened log file {self.filepath} at offset {self._last_offset}")
                    except Exception as e:
                        logger.warning(f"Failed to open log file {self.filepath}: {e}")
                        await asyncio.sleep(self.poll_interval_sec)
                        continue

                # Check rotation (inode changed)
                if current_inode != self._last_inode and current_inode != (0, 0):
                    logger.info("File rotation detected. Reopening new file from offset 0.")
                    self._file_obj.close()
                    self._file_obj = open(self.filepath, "r", encoding="utf-8", errors="replace")
                    self._last_inode = current_inode
                    self._last_offset = 0
                    partial_line_buffer = ""

                # Check truncation (file size shrank)
                if stat.st_size < self._last_offset:
                    logger.info("File truncation detected. Seeking to offset 0.")
                    self._file_obj.seek(0, os.SEEK_SET)
                    self._last_offset = 0
                    partial_line_buffer = ""

                # Read available chunks
                chunk = self._file_obj.read(1024 * 512) # 512 KB chunk
                if chunk:
                    self._last_offset = self._file_obj.tell()
                    content = partial_line_buffer + chunk
                    lines = content.split("\n")
                    # If the last item doesn't end in newline, keep as partial buffer
                    partial_line_buffer = lines[-1]
                    complete_lines = lines[:-1]

                    for line in complete_lines:
                        clean_line = line.strip()
                        if clean_line:
                            self.total_lines_read += 1
                            try:
                                self.queue.put_nowait(clean_line)
                            except asyncio.QueueFull:
                                self.dropped_lines += 1
                                try:
                                    self.queue.get_nowait()
                                    self.queue.put_nowait(clean_line)
                                except Exception:
                                    pass

                await asyncio.sleep(self.poll_interval_sec)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in FileTailer loop: {e}", exc_info=True)
                await asyncio.sleep(self.poll_interval_sec)

        if self._file_obj:
            try:
                self._file_obj.close()
                self._file_obj = None
            except Exception:
                pass
