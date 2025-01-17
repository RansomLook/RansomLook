#!/usr/bin/env python3

import asyncio
import logging
import os
import signal
import time
from abc import ABC
from datetime import datetime, timedelta
from subprocess import Popen
from typing import List, Optional, Tuple

from valkey import Valkey # type: ignore
from valkey.exceptions import ConnectionError as ValkeyConnectionError # type: ignore

from .config import get_socket_path


class AbstractManager(ABC):

    script_name: str

    def __init__(self, loglevel: int=logging.DEBUG) -> None:
        self.loglevel = loglevel
        self.logger = logging.getLogger(f'{self.__class__.__name__}')
        self.logger.setLevel(loglevel)
        self.logger.info(f'Initializing {self.__class__.__name__}')
        self.process: Optional[Popen] = None # type: ignore[type-arg]
        self.__valkey = Valkey(unix_socket_path=get_socket_path('cache'), db=1, decode_responses=True)

        self.force_stop = False

    @staticmethod
    def is_running() -> List[Tuple[str, float]]:
        try:
            valkey_handle = Valkey(unix_socket_path=get_socket_path('cache'), db=1, decode_responses=True)
            for script_name, score in valkey_handle.zrangebyscore('running', '-inf', '+inf', withscores=True):
                for pid in valkey_handle.smembers(f'service|{script_name}'):
                    try:
                        os.kill(int(pid), 0)
                    except OSError:
                        print(f'Got a dead script: {script_name} - {pid}')
                        valkey_handle.srem(f'service|{script_name}', pid)
                        other_same_services = valkey_handle.scard(f'service|{script_name}')
                        if other_same_services:
                            valkey_handle.zadd('running', {script_name: other_same_services})
                        else:
                            valkey_handle.zrem('running', script_name)
            return valkey_handle.zrangebyscore('running', '-inf', '+inf', withscores=True)
        except ValkeyConnectionError:
            print('Unable to connect to valkey, the system is down.')
            return []

    @staticmethod
    def clear_running() -> None:
        try:
            valkey_handle = Valkey(unix_socket_path=get_socket_path('cache'), db=1, decode_responses=True)
            valkey_handle.delete('running')
        except ValkeyConnectionError:
            print('Unable to connect to valkey, the system is down.')

    @staticmethod
    def force_shutdown() -> None:
        try:
            valkey_handle = Valkey(unix_socket_path=get_socket_path('cache'), db=1, decode_responses=True)
            valkey_handle.set('shutdown', 1)
        except ValkeyConnectionError:
            print('Unable to connect to valkey, the system is down.')

    def set_running(self) -> None:
        self.__valkey.zincrby('running', 1, self.script_name)
        self.__valkey.sadd(f'service|{self.script_name}', os.getpid())

    def unset_running(self) -> None:
        current_running = self.__valkey.zincrby('running', -1, self.script_name)
        if int(current_running) <= 0:
            self.__valkey.zrem('running', self.script_name)

    def long_sleep(self, sleep_in_sec: int, shutdown_check: int=10) -> bool:
        shutdown_check = min(sleep_in_sec, shutdown_check)
        sleep_until = datetime.now() + timedelta(seconds=sleep_in_sec)
        while sleep_until > datetime.now():
            time.sleep(shutdown_check)
            if self.shutdown_requested():
                return False
        return True

    async def long_sleep_async(self, sleep_in_sec: int, shutdown_check: int=10) -> bool:
        shutdown_check = min(sleep_in_sec, shutdown_check)
        sleep_until = datetime.now() + timedelta(seconds=sleep_in_sec)
        while sleep_until > datetime.now():
            await asyncio.sleep(shutdown_check)
            if self.shutdown_requested():
                return False
        return True

    def shutdown_requested(self) -> bool:
        try:
            return bool(self.__valkey.exists('shutdown'))
        except ConnectionRefusedError:
            return True
        except ValkeyConnectionError:
            return True

    def _to_run_forever(self) -> None:
        raise NotImplementedError('This method must be implemented by the child')

    def _kill_process(self) -> None:
        if self.process is None:
            return
        kill_order = [signal.SIGWINCH, signal.SIGTERM, signal.SIGINT, signal.SIGKILL]
        for sig in kill_order:
            if self.process.poll() is None:
                self.logger.info(f'Sending {sig} to {self.process.pid}.')
                self.process.send_signal(sig)
                time.sleep(1)
            else:
                break
        else:
            self.logger.warning(f'Unable to kill {self.process.pid}, keep sending SIGKILL')
            while self.process.poll() is None:
                self.process.send_signal(signal.SIGKILL)
                time.sleep(1)

    def run(self, sleep_in_sec: int) -> None:
        self.logger.info(f'Launching {self.__class__.__name__}')
        try:
            while not self.force_stop:
                if self.shutdown_requested():
                    break
                try:
                    if self.process:
                        if self.process.poll() is not None:
                            self.logger.critical(f'Unable to start {self.script_name}.')
                            break
                    else:
                        self.set_running()
                        self._to_run_forever()
                except Exception:  # nosec B110
                    self.logger.exception(f'Something went terribly wrong in {self.__class__.__name__}.')
                finally:
                    if not self.process:
                        # self.process means we run an external script, all the time,
                        # do not unset between sleep.
                        self.unset_running()
                if not self.long_sleep(sleep_in_sec):
                    break
        except KeyboardInterrupt:
            self.logger.warning(f'{self.script_name} killed by user.')
        finally:
            if self.process:
                self._kill_process()
            try:
                self.unset_running()
            except Exception:  # nosec B110
                # the services can already be down at that point.
                pass
            self.logger.info(f'Shutting down {self.__class__.__name__}')

    async def stop(self) -> None:
        self.force_stop = True

    async def _to_run_forever_async(self) -> None:
        raise NotImplementedError('This method must be implemented by the child')

    async def _wait_to_finish(self) -> None:
        self.logger.info('Not implemented, nothing to wait for.')

    async def stop_async(self) -> None:
        """Method to pass the signal handler:
            loop.add_signal_handler(signal.SIGTERM, lambda: loop.create_task(p.stop()))
        """
        self.force_stop = True

    async def run_async(self, sleep_in_sec: int) -> None:
        self.logger.info(f'Launching {self.__class__.__name__}')
        try:
            while not self.force_stop:
                if self.shutdown_requested():
                    break
                try:
                    if self.process:
                        if self.process.poll() is not None:
                            self.logger.critical(f'Unable to start {self.script_name}.')
                            break
                    else:
                        self.set_running()
                        await self._to_run_forever_async()
                except Exception:  # nosec B110
                    self.logger.exception(f'Something went terribly wrong in {self.__class__.__name__}.')
                finally:
                    if not self.process:
                        # self.process means we run an external script, all the time,
                        # do not unset between sleep.
                        self.unset_running()
                if not await self.long_sleep_async(sleep_in_sec):
                    break
        except KeyboardInterrupt:
            self.logger.warning(f'{self.script_name} killed by user.')
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
            self.logger.info(f'Shutting down {self.__class__.__name__}')
