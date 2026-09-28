import os
import asyncio
import tempfile
import pytest
from app.tailer import FileTailer


@pytest.mark.asyncio
async def test_tailer_reads_appended_lines():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "app.log")
        with open(path, "w", encoding="utf-8") as f:
            f.write("first complete line\n")

        tailer = FileTailer(path, poll_interval_sec=0.02, from_start=True, queue_size=100)
        await tailer.start()
        try:
            first = await asyncio.wait_for(tailer.get_line(), timeout=2.0)
            assert "first complete line" in first

            with open(path, "a", encoding="utf-8") as f:
                f.write("second complete line\n")
                f.flush()

            second = await asyncio.wait_for(tailer.get_line(), timeout=2.0)
            assert "second complete line" in second
        finally:
            await tailer.stop()


@pytest.mark.asyncio
async def test_tailer_buffers_partial_line():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "app.log")
        with open(path, "w", encoding="utf-8") as f:
            f.write("")

        tailer = FileTailer(path, poll_interval_sec=0.02, from_start=True, queue_size=100)
        await tailer.start()
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write("incomplete without newline")
                f.flush()

            await asyncio.sleep(0.12)
            assert tailer.queue.empty()

            with open(path, "a", encoding="utf-8") as f:
                f.write(" now complete\n")
                f.flush()

            line = await asyncio.wait_for(tailer.get_line(), timeout=2.0)
            assert "incomplete without newline now complete" in line
        finally:
            await tailer.stop()


@pytest.mark.asyncio
async def test_tailer_handles_truncation():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "app.log")
        with open(path, "w", encoding="utf-8") as f:
            f.write("old line\n")

        tailer = FileTailer(path, poll_interval_sec=0.02, from_start=True, queue_size=100)
        await tailer.start()
        try:
            old = await asyncio.wait_for(tailer.get_line(), timeout=2.0)
            assert "old line" in old

            # Shrink below last offset so truncation is detected, then write the new line
            with open(path, "w", encoding="utf-8") as f:
                f.write("")
                f.flush()
            await asyncio.sleep(0.08)
            with open(path, "a", encoding="utf-8") as f:
                f.write("after truncate\n")
                f.flush()

            new = await asyncio.wait_for(tailer.get_line(), timeout=2.0)
            assert "after truncate" in new
        finally:
            await tailer.stop()
