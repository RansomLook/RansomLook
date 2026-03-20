#!/usr/bin/env python3

import asyncio
import logging
import os
import signal
import time
from abc import ABC
from datetime import datetime, timedelta
from subprocess import Popen

from valkey import Valkey
from valkey.exceptions import ConnectionError as ValkeyConnectionError

from . import DB_TASKS
from .config import get_socket_path
from .logging import get_logger

_logger = get_logger("abstractmanager")


class AbstractManager(ABC):
    script_name: str

    def __init__(self, loglevel: int = logging.DEBUG) -> None:
        self.loglevel = loglevel
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
        self.logger.setLevel(loglevel)
        self.logger.info("Initializing %s", self.__class__.__name__)
        self.process: Popen | None = None  # type: ignore[type-arg]
        self.__redis = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_TASKS, decode_responses=True)

        self.force_stop = False

    @staticmethod
    def is_running() -> list[tuple[str, float]]:
        try:
            r = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_TASKS, decode_responses=True)
            for script_name, score in r.zrangebyscore("running", "-inf", "+inf", withscores=True):  # type: ignore[union-attr]
                pids = list(r.smembers(f"service|{script_name}"))  # type: ignore[arg-type]
                dead_pids = []
                for pid in pids:
                    try:
                        os.kill(int(pid), 0)
                    except OSError:
                        dead_pids.append(pid)

                for pid in dead_pids:
                    _logger.warning("Got a dead script: %s - %s", script_name, pid)
                    r.srem(f"service|{script_name}", pid)

                alive = r.scard(f"service|{script_name}")
                if alive:
                    r.zadd("running", {script_name: alive})  # type: ignore[dict-item]
                else:
                    r.zrem("running", script_name)
            return r.zrangebyscore("running", "-inf", "+inf", withscores=True)  # type: ignore[return-value]
        except ValkeyConnectionError:
            _logger.error("Unable to connect to redis, the system is down.")
            return []

    @staticmethod
    def clear_running() -> None:
        try:
            r = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_TASKS, decode_responses=True)
            r.delete("running")
        except ValkeyConnectionError:
            _logger.error("Unable to connect to redis, the system is down.")

    @staticmethod
    def force_shutdown() -> None:
        try:
            r = Valkey(unix_socket_path=get_socket_path("cache"), db=DB_TASKS, decode_responses=True)
            r.set("shutdown", 1)
        except ValkeyConnectionError:
            _logger.error("Unable to connect to redis, the system is down.")

    def set_running(self) -> None:
        self.__redis.zincrby("running", 1, self.script_name)
        self.__redis.sadd(f"service|{self.script_name}", os.getpid())

    def unset_running(self) -> None:
        current_running = self.__redis.zincrby("running", -1, self.script_name)
        if int(current_running) <= 0:  # type: ignore[arg-type]
            self.__redis.zrem("running", self.script_name)

    def long_sleep(self, sleep_in_sec: int, shutdown_check: int = 10) -> bool:
        shutdown_check = min(sleep_in_sec, shutdown_check)
        sleep_until = datetime.now() + timedelta(seconds=sleep_in_sec)
        while sleep_until > datetime.now():
            time.sleep(shutdown_check)
            if self.shutdown_requested():
                return False
        return True

    async def long_sleep_async(self, sleep_in_sec: int, shutdown_check: int = 10) -> bool:
        shutdown_check = min(sleep_in_sec, shutdown_check)
        sleep_until = datetime.now() + timedelta(seconds=sleep_in_sec)
        while sleep_until > datetime.now():
            await asyncio.sleep(shutdown_check)
            if self.shutdown_requested():
                return False
        return True

    def shutdown_requested(self) -> bool:
        try:
            return bool(self.__redis.exists("shutdown"))
        except ConnectionRefusedError:
            return True
        except ValkeyConnectionError:
            return True

    def _to_run_forever(self) -> None:
        raise NotImplementedError("This method must be implemented by the child")

    def _kill_process(self) -> None:
        if self.process is None:
            return
        kill_order = [signal.SIGWINCH, signal.SIGTERM, signal.SIGINT, signal.SIGKILL]
        for sig in kill_order:
            if self.process.poll() is None:
                self.logger.info("Sending %s to %s.", sig, self.process.pid)
                self.process.send_signal(sig)
                time.sleep(1)
            else:
                break
        else:
            self.logger.warning("Unable to kill %s, keep sending SIGKILL", self.process.pid)
            while self.process.poll() is None:
                self.process.send_signal(signal.SIGKILL)
                time.sleep(1)

    def run(self, sleep_in_sec: int) -> None:
        self.logger.info("Launching %s", self.__class__.__name__)
        try:
            while not self.force_stop:
                if self.shutdown_requested():
                    break
                try:
                    if self.process:
                        if self.process.poll() is not None:
                            self.logger.critical("Unable to start %s.", self.script_name)
                            break
                    else:
                        self.set_running()
                        self._to_run_forever()
                except Exception:  # nosec B110
                    self.logger.exception("Something went terribly wrong in %s.", self.__class__.__name__)
                finally:
                    if not self.process:
                        # self.process means we run an external script, all the time,
                        # do not unset between sleep.
                        self.unset_running()
                if not self.long_sleep(sleep_in_sec):
                    break
        except KeyboardInterrupt:
            self.logger.warning("%s killed by user.", self.script_name)
        finally:
            if self.process:
                self._kill_process()
            try:
                self.unset_running()
            except Exception:  # nosec B110
                # the services can already be down at that point.
                pass
            self.logger.info("Shutting down %s", self.__class__.__name__)

    async def stop(self) -> None:
        self.force_stop = True

    async def _to_run_forever_async(self) -> None:
        raise NotImplementedError("This method must be implemented by the child")

    async def _wait_to_finish(self) -> None:
        self.logger.info("Not implemented, nothing to wait for.")

    async def stop_async(self) -> None:
        """Method to pass the signal handler:
        loop.add_signal_handler(signal.SIGTERM, lambda: loop.create_task(p.stop()))
        """
        self.force_stop = True

    async def run_async(self, sleep_in_sec: int) -> None:
        self.logger.info("Launching %s", self.__class__.__name__)
        try:
            while not self.force_stop:
                if self.shutdown_requested():
                    break
                try:
                    if self.process:
                        if self.process.poll() is not None:
                            self.logger.critical("Unable to start %s.", self.script_name)
                            break
                    else:
                        self.set_running()
                        await self._to_run_forever_async()
                except Exception:  # nosec B110
                    self.logger.exception("Something went terribly wrong in %s.", self.__class__.__name__)
                finally:
                    if not self.process:
                        # self.process means we run an external script, all the time,
                        # do not unset between sleep.
                        self.unset_running()
                if not await self.long_sleep_async(sleep_in_sec):
                    break
        except KeyboardInterrupt:
            self.logger.warning("%s killed by user.", self.script_name)
        except Exception as e:  # nosec B110
            self.logger.exception(e)
        finally:
            await self._wait_to_finish()
            if self.process:
                self._kill_process()
            try:
                self.unset_running()
            except Exception:  # nosec B110
                # the services can already be down at that point.
                pass
            self.logger.info("Shutting down %s", self.__class__.__name__)
