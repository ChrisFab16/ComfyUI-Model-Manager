import asyncio
import threading
import queue
import time

from . import utils


class DownloadThreadPool:
    def __init__(self) -> None:
        self.workers_count = 0
        self.task_queue = queue.Queue()
        self.running_tasks = set()
        self._lock = threading.Lock()
        self._shutdown = False

        default_max_workers = 5
        max_workers: int = default_max_workers
        self.max_worker = max_workers

    def submit(self, task, task_id):
        with self._lock:
            if task_id in self.running_tasks:
                return "Existing"
            self.running_tasks.add(task_id)
        
        self.task_queue.put((task, task_id))
        return self._adjust_worker_count()

    def _adjust_worker_count(self):
        with self._lock:
            if self.workers_count < self.max_worker and not self._shutdown:
                self._start_worker()
                return "Running"
            else:
                return "Waiting"

    def _start_worker(self):
        t = threading.Thread(target=self._worker, daemon=True)
        t.start()
        self.workers_count += 1

    def _worker(self):
        """Non-blocking worker that processes tasks without blocking UI"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            while not self._shutdown:
                try:
                    # Non-blocking get with timeout to prevent indefinite blocking
                    task, task_id = self.task_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                try:
                    # Run task with proper error handling
                    asyncio.run_coroutine_threadsafe(
                        self._run_task_safely(task, task_id, loop), loop
                    ).result(timeout=300)  # 5 minute timeout per task
                        
                except asyncio.TimeoutError:
                    utils.print_error(f"Task {task_id} timed out after 5 minutes")
                except Exception as e:
                    utils.print_error(f"Worker task error: {str(e)}")
                finally:
                    # Always clean up task from running set
                    with self._lock:
                        self.running_tasks.discard(task_id)
                    
                    # Mark task as done for queue
                    self.task_queue.task_done()
                    
        finally:
            loop.close()
            with self._lock:
                self.workers_count -= 1

    async def _run_task_safely(self, task, task_id, loop):
        """Safely run task with proper async handling"""
        try:
            # If task is a coroutine, await it directly
            if asyncio.iscoroutinefunction(task):
                await task(task_id)
            else:
                # If task is sync, run in executor to prevent blocking
                await loop.run_in_executor(None, task, task_id)
        except Exception as e:
            utils.print_error(f"Task {task_id} failed: {str(e)}")
            raise

    def shutdown(self):
        """Gracefully shutdown the thread pool"""
        with self._lock:
            self._shutdown = True
        
        # Wait for all tasks to complete (with timeout)
        try:
            self.task_queue.join()  # Wait for all tasks to be marked as done
        except:
            pass

    def get_status(self):
        """Get current thread pool status"""
        with self._lock:
            return {
                "workers_count": self.workers_count,
                "max_workers": self.max_worker,
                "running_tasks": len(self.running_tasks),
                "queued_tasks": self.task_queue.qsize(),
                "shutdown": self._shutdown
            }