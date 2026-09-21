# README.md

# Exercise 2 — Synchronization & Custom I/O

## Due Date
19.05.2026

## Overview
You will solve the same problem **three times**, each time with a different operating-system paradigm:

1. **Part 1 — Naive Processes:** observe the chaos of unsynchronized concurrent file writes.
2. **Part 2 — Threads + Mutex:** synchronize a shared *memory* space.
3. **Part 3 — Processes + System V Semaphore:** synchronize a shared *OS resource* (the file offset).

By the end of the assignment you will understand:
- How `dup2()` redirection works (`open` + `dup2` + write to `stdout`).
- How a stdio-style buffer works under the hood (and why one is needed).
- The crucial difference between protecting **memory** (mutex around buffer state) and protecting an **OS resource** (semaphore around an inter-process write path).

> **Schedule note.** Parts 1 and 2 use only material covered up to the **fork/exec/wait** and **threads/POSIX/mutex** sessions. Part 3 requires **semaphores**, which is the final TA session before the assignment is due. You are strongly encouraged to finish Parts 1 and 2 *before* the semaphores lecture.

## Repository Layout
```
.
├── README.md            — this file (read FIRST — contains the shared requirements)
├── Part1.md             — naive processes
├── Part2.md             — threads + mutex
├── Part3.md             — processes + named semaphore
├── REPORT.md            — optional report (small bonus available)
├── src/
│   ├── part1.c          — your code (stub provided)
│   ├── part2.c          — your code (stub provided)
│   ├── part3.c          — your code (stub provided)
│   └── Makefile
└── tests/
    └── sanity.py        — sanity check; run before submitting
```

## How to Read This Assignment
1. Read this README **end to end** — sections "Shared Requirements" through "Forbidden / Allowed" apply to all parts.
2. Then read `Part1.md`, `Part2.md`, `Part3.md` in order.
3. Implement the parts in order. The three `partN.c` files are independent (each has its own `main`), but they share the same buffer logic, output format, command-line interface, and error-handling rules. **Reuse your own code** between parts — only the synchronization layer should change.

## Build & Run
```bash
cd src
make                    # builds part1, part2, part3
./part1 "Hello" 4 100   # runs part1 with 4 workers writing 100 messages each
cat output.txt          # see what happened
```

## Sanity Check
Before submitting, run:
```bash
python3 tests/sanity.py
```
This compiles your code and runs each part with small inputs, confirming the basics: it builds without warnings, the binaries run, the output has the right shape, and the timing line is on stderr.

**This is not a grader.** Passing it just means your code is not obviously broken — it doesn't guarantee a passing grade. Edge cases, stress loads, and forbidden-API checks happen separately during grading.

## Deliverables
Push to your GitHub Classroom repository before the deadline:
1. id.txt - a .txt file containing the last 5 digits of your ID
2. `src/part1.c`, `src/part2.c`, `src/part3.c` — your three implementations.
3. `src/Makefile` — must build all three with `make`.
4. *(Optional)* `REPORT.md` — fill in for up to +5 bonus points (capped at 100 total).

Do **not** commit binaries (`part1`, `part2`, `part3`) or `output.txt`. A `.gitignore` is provided.

---

# Shared Requirements

These apply to **all three parts**. Each `partN.c` is an independent file with its own `main()`, but the buffer logic, output format, command-line interface, timing, and error-handling rules below are identical across all three. The only thing that differs between parts is the synchronization layer (and processes vs threads).

## 1. System-Level Output Redirection

You may **not** use `fopen`, `fprintf` (to anything other than `stderr`), `fwrite`, or any other stdio function for writing to `output.txt`.

The parent process must:
1. Open `output.txt` with the raw `open()` system call:
   ```c
   int fd = open("output.txt", O_WRONLY | O_CREAT | O_TRUNC, 0644);
   ```
2. Redirect `STDOUT_FILENO` (file descriptor `1`) to that file:
   ```c
   if (dup2(fd, STDOUT_FILENO) == -1) { perror("dup2"); /* ... */ }
   close(fd);
   ```
3. From that point on, **every byte written via `write(STDOUT_FILENO, …)` ends up in `output.txt`.**

This redirection happens in the parent **before** any child process is forked or any thread is created, so all workers inherit the redirected stdout.

> Why this matters: when you `fork()`, the child inherits a *copy* of the file-descriptor table that points to the **same entry in the open file table** (and therefore the same offset). Multiple processes writing to fd 1 are all racing on the same offset. This is the exact phenomenon Part 1 demonstrates and Part 3 fixes.

## 2. The Custom Buffer

You are forbidden from calling `write()` once per character or once per message. You must implement a fixed-size buffering layer.

### Required globals (do not rename or resize)
```c
#define CHUNK_SIZE 64
char buffer[CHUNK_SIZE];
int  buffer_pos = 0;
```

### `my_write(const char *str)`
Copies the bytes of `str` (excluding the terminating `\0`) into `buffer`. Behaviour:

- Copy as many bytes as fit into the remaining space in `buffer`.
- **Flush rule:** call the actual `write(STDOUT_FILENO, buffer, CHUNK_SIZE)` system call **only when the buffer becomes completely full** (i.e. `buffer_pos == CHUNK_SIZE`). After flushing, reset `buffer_pos = 0`.
- **Partial writes:** if the input string is larger than the remaining space in the buffer, fill the buffer to the brim, flush it, and then continue copying the remaining bytes (recursing if necessary — the rest of the string itself may be larger than `CHUNK_SIZE`).

### `flush_buffer(void)`
Writes the *first `buffer_pos` bytes* of `buffer` to `STDOUT_FILENO` (this is the "non-full flush" used at end of execution). Resets `buffer_pos` to `0`. Must handle short writes (i.e. `write()` returning fewer bytes than requested) by looping.

### Why `CHUNK_SIZE = 64`?
A formatted line (see §3) is roughly 50 bytes long. With a 64-byte chunk, **most flushes will split a message**: the boundary between two flushes will fall in the middle of a line. This is intentional. Without it, Part 1's chaos would be invisible (each message would happen to fit cleanly in one `write()` call).

You will revisit `CHUNK_SIZE` in your performance analysis (see `REPORT.md`, optional).

## 3. The Output Format (STRICT)

Every line written by a worker must be produced by `snprintf` into a local buffer and then passed to `my_write`. The format is:

```
[Type: <PROCESS|THREAD>] [ID: <worker_id>] [Seq: <seq_number>] <message>\n
```

Field rules:
| Field | Format specifier | Notes |
|---|---|---|
| Type | `PROCESS` or `THREAD` literal | `PROCESS` for parts 1 & 3; `THREAD` for part 2. Uppercase. |
| ID   | `%d` | 0-indexed: `0 .. num_workers-1`. |
| Seq  | `%03d` | 0-indexed, zero-padded to 3 digits: `000 .. writes_per_worker-1`. |
| message | `%s` | The user-supplied message string, no trailing newline. |

Example:
```
[Type: THREAD] [ID: 2] [Seq: 045] Hello, world!
```

Each line is validated against this exact regex:
```
^\[Type: (PROCESS|THREAD)\] \[ID: (\d+)\] \[Seq: (\d{3})\] (.+)\n$
```

> Note the exact spacing: one space inside each `[ … ]` separator, single spaces between fields, single `\n` at end. `\t` will fail. Trailing spaces will fail.

## 4. Command-Line Arguments

Every part's `main()` must accept exactly:

```
./partN <message> <num_workers> <writes_per_worker>
```

- `<message>` — an arbitrary string, *guaranteed not to contain* `\n` or NUL.
- `<num_workers>` — a positive integer.
- `<writes_per_worker>` — a positive integer.

If `argc != 4`, print
```
Usage: <argv[0]> <message> <num_workers> <writes_per_worker>
```
to **stderr** and exit with status `1`.

Reject non-positive integers with a clear error message to stderr and exit status `1`.

## 5. Timing & Performance Reporting

The parent process must:
1. Record a start timestamp **just before** spawning workers, using `gettimeofday()` or `clock_gettime(CLOCK_MONOTONIC, …)`.
2. Record an end timestamp **just after** all workers have finished and all buffers are flushed.
3. Print the elapsed wall-clock time in **milliseconds** to **`stderr`** (so it doesn't pollute `output.txt`):
   ```
   elapsed_ms=12.345
   ```
   The exact format is `elapsed_ms=<float>` with 3 decimal places.

## 6. Error Handling

Every system call (`open`, `dup2`, `fork`, `pthread_create`, `pthread_join`, `pthread_mutex_init`, `semget`, `semop`, `semctl`, `ftok`, `wait`, `waitpid`, `write`, `read`, `close`, …) must be checked. On failure, call `perror("<syscall-name>")` and exit with a non-zero status.

A "checked" call looks like this:
```c
pid_t pid = fork();
if (pid == -1) { perror("fork"); exit(1); }
```

## 7. Cleanup

The program must leave the system in a clean state:
- All file descriptors opened by the parent are closed before exit.
- All threads are joined (Part 2).
- All children are reaped via `wait()` / `waitpid()` (Parts 1 & 3) — **no zombies**.
- All mutexes are destroyed (Part 2).
- The System V semaphore is removed via `semctl(semid, 0, IPC_RMID)` by the parent (Part 3) so it does not linger in the kernel IPC table. After exit, `ipcs -s` should show no leftover semaphore.

---

## Forbidden / Allowed (Summary)

- ❌ `fopen`, `fprintf` (to anything other than `stderr`), `fwrite`, `fputs`, `puts`, `printf`. You must use `open` + `dup2` + raw `write()` (wrapped by `my_write`).
- ❌ Any third-party libraries.
- ❌ Locks of any kind in Part 1.
- ❌ `pthread_*` in Parts 1 and 3.
- ❌ POSIX `sem_*` (`sem_open`, `sem_wait`, `sem_post`, etc.) anywhere — Part 3 uses **System V** semaphores (`semget`, `semop`, `semctl`).
- ❌ System V semaphore calls (`semget`, `semop`, `semctl`) in Parts 1 and 2.
- ❌ File-locking (`flock`, `fcntl(F_SETLK)`) anywhere.
- ✅ `fprintf(stderr, …)` is fine (e.g., for the timing message and error reporting).
- ✅ `snprintf` for formatting strings before passing them to `my_write`.
- ✅ Reusing your own `my_write` / `flush_buffer` code across the three parts.

## Submission Workflow (GitHub Classroom)
1. Accept the assignment via the Classroom link.
2. Clone your repository.
3. Implement, test locally with `python3 tests/sanity.py`, commit, and push.

Good luck — and remember: **the chaos in Part 1 is a feature, not a bug**. Stare at it until you understand exactly *why* it happens. That understanding is what Parts 2 and 3 are there to fix.

---

# Part1.md

# Part 1 — The Baseline (Naive Processes)

## Objective
Demonstrate, in your own working code, the chaos that arises when concurrent processes write to the same file descriptor without any synchronization.

## Architecture
1. The **parent** sets up the redirection (open + dup2) and parses argv.
2. The parent records the start timestamp.
3. The parent loops `num_workers` times and calls `fork()` each iteration.
4. Each child runs the worker routine: a loop of `writes_per_worker` iterations, each iteration formats a message via `snprintf` and calls `my_write`. After the loop, the child calls `flush_buffer` and `_exit(0)`.
5. The parent waits for every child via `wait()` / `waitpid()`.
6. The parent records the end timestamp and reports it to **stderr**.

## Required: Fork All Before Wait
You **must** fork all `num_workers` children before calling any `wait()`. The following pattern is forbidden because it serializes execution and hides the chaos:

```c
// FORBIDDEN
for (int i = 0; i < num_workers; i++) {
    pid = fork();
    if (pid == 0) { worker(...); _exit(0); }
    waitpid(pid, NULL, 0);   // <— this waits BEFORE forking the next child
}
```

The correct pattern is:

```c
pid_t pids[num_workers];
for (int i = 0; i < num_workers; i++) {
    pids[i] = fork();
    if (pids[i] == -1) { perror("fork"); /* ... */ }
    if (pids[i] == 0) { worker(i, message, writes_per_worker); _exit(0); }
}
for (int i = 0; i < num_workers; i++) {
    if (waitpid(pids[i], NULL, 0) == -1) { perror("waitpid"); /* ... */ }
}
```

## Synchronization
**None.** No mutexes, no semaphores, no lock files, no `sleep` to space out writes. The whole point of this part is to observe what happens *without* synchronization.

You **may** use `wait()` at the end, of course — that is reaping, not synchronization.

## Workers Use `_exit`, Not `exit`
A child should call `_exit(0)` after `flush_buffer()`, **not** `exit(0)`. `exit()` runs `atexit` handlers and stdio cleanup, which can flush stdio buffers in a way that interacts badly with our manual buffering. (Try replacing `_exit` with `exit` later and see what changes — it's an interesting experiment.)

## Expected Output
With `CHUNK_SIZE=64` and a typical message of 10–20 chars, you should observe in `output.txt`:

- Some lines that are perfectly well-formed.
- Some lines that contain the *tail* of one worker's message immediately followed by the *head* of another's, with no `\n` separator.
- Some lines whose `[Type: …] [ID: …] [Seq: …] …` header is itself sliced across two workers' interleaved chunks.
- The total byte count will be exactly the same as a fully synchronized run (no bytes are lost — they're just interleaved).

This is **not** a bug in your code. It is the system telling you the truth about what happens when multiple processes share a file offset and nobody is mediating.

## Optional: What to Put in REPORT.md for Part 1
*(REPORT.md is optional; filling it in earns up to +5 bonus points capped at 100. Skip this section if you don't plan to fill in the report.)*
Run:
```bash
./part1 "Hello concurrent world" 4 50
```
1. Paste a 5–10-line excerpt from `output.txt` that clearly shows interleaving.
2. In one paragraph, explain *why* the interleaving happens. Specifically address: where does the buffer live in memory after `fork()`? Where does the file offset live? Which one is shared?

## Acceptance Criteria (Autograder)
- Compiles cleanly with `-Wall -Wextra` (no warnings).
- Exits with status 0 on valid input.
- Total output bytes equal `num_workers × writes_per_worker × len(formatted_line)`.
- Every fork/waitpid/dup2/open/write call is `perror`-checked.

## Forbidden in Part 1
- `pthread_*`
- `sem_*`
- File-locking (`flock`, `fcntl(F_SETLK)`, lockfiles, …)
- `sleep`/`usleep` used as a synchronization device. (Sleeping for debugging output is fine but pointless here.)
- Any form of `fopen`/`fprintf`/`puts`/etc. for `output.txt`.

---

# Part2.md

# Part 2 — Shared Memory Crisis (Threads + Mutex)

## Objective
Switch from processes to threads, and learn that the failure mode changes. Threads share the entire address space, so they share the buffer too. Now the corruption isn't only at the file offset — it's *inside the buffer itself*.

## Architecture
1. The **parent thread** (i.e. `main`) sets up redirection, parses argv, records start time.
2. The parent creates `num_workers` POSIX threads via `pthread_create`. Each thread runs a worker routine.
3. Each thread loops `writes_per_worker` times, formats a message via `snprintf` into a local buffer, and calls `my_write`.
4. The parent joins every thread with `pthread_join`.
5. The parent calls `flush_buffer()` once after all joins (to flush any tail bytes that didn't make it to a full chunk).
6. The parent records end time and reports to stderr.

## The Crisis (Read This Carefully)
With `fork()` (Part 1 / Part 3) each child gets its **own copy** of `buffer` and `buffer_pos`. The race is on the file offset only.

With `pthread_create` (this part) **all threads share the same `buffer` and `buffer_pos`**. This is much worse:
- Two threads may simultaneously increment `buffer_pos` and *both* think they own the slot, overwriting each other's bytes.
- One thread may be mid-copy when another flushes the buffer out from under it, sending half-formed data to the file *and* leaving the writer's loop pointing at garbage.
- One thread may flush, reset `buffer_pos` to `0`, and then a second thread's lingering write lands beyond the new `buffer_pos`, leaving holes filled with whatever was there before.

The fix is to make `my_write`'s body a **critical section**.

## Synchronization Requirement: One Mutex Around Buffer Manipulation
Use a single global `pthread_mutex_t` to protect everything that touches `buffer` or `buffer_pos`:

```c
pthread_mutex_t buf_mtx = PTHREAD_MUTEX_INITIALIZER;

static void my_write(const char *str) {
    pthread_mutex_lock(&buf_mtx);
    /* copy bytes; flush if buffer becomes full */
    pthread_mutex_unlock(&buf_mtx);
}
```

The lock must be **held for the duration of any access to `buffer`/`buffer_pos`**, including the flush call (`write(STDOUT_FILENO, buffer, CHUNK_SIZE)`) and the subsequent reset. You cannot drop the lock between "I see the buffer is full" and "I flush it" — that would re-introduce the race.

> **Conceptual question (the optional REPORT.md asks about this):** Could you make this lock *narrower* — for example, lock only the increment of `buffer_pos`, then drop the lock, then do the actual byte copy? Try it on paper. What goes wrong? (Hint: think about a context switch right after the increment.)

> **Note for Part 3.** In Part 3 the lock will look almost identical to this one — wrapping the whole `my_write` — but the **primitive** changes (named semaphore instead of mutex), and there is a subtle extra requirement that the buffer be *drained* before releasing the lock. The reason will become clear when you write it. Hold this thought.

## Cleanup Requirements
- All threads must be joined.
- The mutex must be destroyed with `pthread_mutex_destroy` before exit.
- The output fd must be closed.

## Build
```bash
gcc -Wall -Wextra -O2 -pthread -o part2 part2.c
```
The provided `Makefile` already does this.

## Optional: What to Put in REPORT.md for Part 2
*(REPORT.md is optional; filling it in earns up to +5 bonus points capped at 100. Skip this section if you don't plan to fill in the report.)*
1. **Output check.** Run `./part2 "Hello threaded world" 4 50 > /dev/null` and confirm `output.txt` is *clean* — every line matches the format. Paste 3 lines as evidence.
2. **Lock-scope question.** Answer the conceptual question above. Be specific about what shared state would race.
3. **CHUNK_SIZE experiment.** Run Part 2 with `./part2 "test" 50 1000` while temporarily changing `CHUNK_SIZE` to `8`, `64`, and `4096`. Report `elapsed_ms` for each. Explain in 2–3 sentences why the timing changes the way it does.

## Acceptance Criteria
- Compiles cleanly with `-Wall -Wextra -pthread` (no warnings).
- Output: every line matches the format regex; every `(ID, Seq)` pair appears **exactly once**; for each `ID` the `Seq` values are exactly `0..writes_per_worker-1`.
- No deadlocks (timeout is generous but enforced).
- Mutex is initialized and destroyed; threads are joined; fd is closed.

## Forbidden in Part 2
- `fork()` (this part is threads-only).
- More than one mutex (we only want the buffer mutex).
- `sem_*`.
- Any condition-variable trickery to "synchronize" the buffer differently. The point is: *one mutex, around the buffer-touching code*.

---

# Part3.md

# Part 3 — Isolated Memory Crisis (Processes + System V Semaphore)

## Objective
Return to processes — but this time, fix the chaos. Discover that even though the buffer is no longer shared (each forked child has its own), you still need a synchronization primitive — and you need a *different kind* than in Part 2, because the resource you are protecting is no longer in your address space.

## The System V Semaphore API in 30 Seconds

System V semaphores are kernel objects identified by an integer **key**. The functions you'll use:

```c
#include <sys/types.h>
#include <sys/ipc.h>
#include <sys/sem.h>

key_t key = ftok(argv[0], 'A');         // derive a key from a stable path
int   semid = semget(key, 1, IPC_CREAT | IPC_EXCL | 0644);  // create one semaphore
                                                             // returns -1 on failure
// initialize value to 1 (so it acts as a binary semaphore / mutex)
union semun { int val; struct semid_ds *buf; unsigned short *array; } arg;
arg.val = 1;
semctl(semid, 0, SETVAL, arg);

// acquire (P-operation): atomically decrement, blocking if value is 0
struct sembuf op_wait = { .sem_num = 0, .sem_op = -1, .sem_flg = 0 };
semop(semid, &op_wait, 1);

// release (V-operation): atomically increment
struct sembuf op_post = { .sem_num = 0, .sem_op = +1, .sem_flg = 0 };
semop(semid, &op_post, 1);

// destroy: remove the semaphore from the kernel IPC table
semctl(semid, 0, IPC_RMID);
```

A few things worth knowing:
- `semget` works with a **set** of semaphores; we ask for a set of size 1 and operate on `sem_num = 0`.
- `union semun` is **not** declared in any header on Linux — you must declare it yourself, exactly as shown above.
- A failed `semget` with `IPC_EXCL` because of a stale leftover from a crashed previous run shows up as `errno == EEXIST`. Handle this: in that case, get the existing semid (call `semget(key, 1, 0)`), remove it with `semctl(..., IPC_RMID)`, and try again. Your program must not crash on a stale leftover.
- The `ftok(path, proj_id)` call hashes the inode of `path` together with `proj_id` to produce a key. Use a path that is guaranteed to exist for the lifetime of the run — `argv[0]` (the program itself) is a good choice.

## Architecture
1. The **parent** sets up redirection, parses argv, records start time.
2. The parent creates a System V semaphore set of size 1, initialized to value 1 (binary mutex). On `EEXIST`, removes the stale set and retries.
3. The parent loops `num_workers` times and `fork()`s. **All children must be forked before any wait**, just like Part 1.
4. Each child runs the worker. It uses the inherited `semid` (an integer — passed via a global or a function argument; either is fine since `fork` duplicates the address space) to lock around the entire body of `my_write`.
5. The parent waits for every child, calls its own final `flush_buffer` (also semaphore-protected), records end time, prints to stderr, removes the semaphore via `IPC_RMID`, and exits.

## The Crisis (And Why It's Different from Part 2)

After `fork()`, each child has its **own private copy** of `buffer` and `buffer_pos`. They cannot corrupt each other's buffers — virtual memory isolates them. So the *memory race* of Part 2 is gone.

But all children share the **same entry in the open file table** (because they inherited fd 1 from the parent). And here's the crucial detail: a single call to `my_write` may trigger **multiple `write()` syscalls** when the input string spans chunk boundaries. For example, with `CHUNK_SIZE=64` and a 50-byte message arriving when `buffer_pos=20`:

```
   [........copy 44 bytes.........] -> buffer full -> write(64)  [SYSCALL #1]
   [..copy remaining 6 bytes...]    -> buffer at pos 6, no flush yet
   ...later, when next message arrives or worker ends...
   [................flush........]  -> write(6)                  [SYSCALL #2]
```

If process A executes SYSCALL #1 and then process B's flush lands *before* A executes SYSCALL #2, the file ends up with A's first 64 bytes, then B's chunk, then A's next 6 bytes — **A's message has been fragmented across the file**. Even though each individual `write()` is atomic at the kernel level on Linux, the *sequence of writes that together produce one logical message* is not.

So the semaphore must protect **the logical unit of work** — the entire `my_write` call — not just the syscall.

## Synchronization Requirement: Semaphore Around the Whole `my_write` Body — *and the Buffer Must Be Drained Before Releasing the Semaphore*

```c
static void my_write(const char *str) {
    struct sembuf op_wait = { 0, -1, 0 };
    struct sembuf op_post = { 0, +1, 0 };

    if (semop(semid, &op_wait, 1) == -1) { perror("semop wait"); _exit(1); }

    /* copy bytes into per-process buffer; flush as it fills */

    /* IMPORTANT: also flush whatever remains in the buffer before releasing,
     * so this process leaves the buffer empty for the next call. */
    if (buffer_pos > 0) {
        write(STDOUT_FILENO, buffer, buffer_pos);   /* + error-check */
        buffer_pos = 0;
    }

    if (semop(semid, &op_post, 1) == -1) { perror("semop post"); _exit(1); }
}
```

`flush_buffer` must also be semaphore-protected for the same reason.

### Why drain the buffer at the end?

In Part 2, only **one** buffer exists (shared between threads). Once the mutex is held, all bytes go through that single buffer in a deterministic order, and the buffer's residual state at the time the lock is released is fine — the next thread to acquire the mutex picks up where the previous one left off.

In Part 3, **each process has its own buffer**. If `my_write` returns with bytes left over in *this process's* buffer (e.g. the message was 50 bytes, and 16 bytes are now sitting in the buffer for next time), then *another process can run, fill its own buffer, and flush a chunk to the shared file before this process gets back* to flush those leftover 16 bytes. The file now contains: \[head of this process's message\] \[other process's chunk\] \[tail of this process's message\] — fragmented across the file, even though each `write()` was atomic and the semaphore was held throughout this process's `my_write`.

The fix is to ensure no carry-over: every `my_write` flushes its own residual bytes before releasing the semaphore. This costs you the ability to amortize syscalls across messages — you'll do roughly one `write()` per `my_write` call — but it's the price of cross-process buffering safety.

The key differences to the previous part are:

| Aspect | Part 2 (threads + mutex) | Part 3 (processes + System V semaphore) |
|---|---|---|
| What's shared between workers? | Everything: `buffer`, `buffer_pos`, fd, file offset | *Only* the fd and its offset (buffers are private) |
| What is the lock protecting? | Memory consistency of `buffer`/`buffer_pos` | Atomicity of a multi-syscall logical message |
| Sync primitive | `pthread_mutex_t` (in-process, user-space) | System V semaphore (kernel IPC object, cross-process) |
| Why this primitive? | Threads share a heap → user-space mutex is fast and sufficient | Processes don't share a heap → mutex in user memory is invisible to other procs → need a kernel object |

This is the central lesson of the exercise: **the choice of synchronization primitive depends on the address-space context, not on the apparent shape of the lock.** A user-space mutex is invisible across processes; a System V semaphore lives in the kernel IPC table and is reachable by any process that holds its `semid`.

## How the Semaphore Survives `fork()`

The `semid` returned by `semget` is just an integer index into a kernel IPC table. After `fork()`, the child inherits the parent's address space — including the integer holding the semid. Both parent and child use the same integer, and `semop`/`semctl` look up the same kernel object. There is nothing in user memory that needs to be shared — the kernel does the work.

> Contrast: a `pthread_mutex_t` placed at the same virtual address in two processes would still be **two different objects**, because each process has its own copy of that memory. That's why mutexes can't synchronize processes (without `mmap(MAP_SHARED)` shenanigans, anyway).

## Cleanup Requirements

This is **more important** than for POSIX semaphores: System V semaphores are stored in a small, system-wide IPC table. A leaked semaphore takes up a slot until the kernel reboots or someone removes it manually with `ipcrm`. On shared lab machines this is a real annoyance.

- The parent must call `semctl(semid, 0, IPC_RMID)` before exiting. Children should **not** call `IPC_RMID` — only the parent.
- After your program exits, `ipcs -s` should not show your semaphore.
- The parent reaps every child (no zombies).
- The output fd is closed.
- Children call `_exit(0)` (not `exit(0)` — same reason as Part 1).
- Handle `EEXIST` from `semget` by removing the stale leftover and retrying, so a previous crash doesn't break this run.

## Build
```bash
gcc -Wall -Wextra -O2 -std=c11 -o part3 part3.c
```
System V semaphore functions are in glibc proper — **no special linker flags needed**. The `Makefile` already builds part3 cleanly.

## Optional: What to Put in REPORT.md for Part 3
*(REPORT.md is optional; filling it in earns up to +5 bonus points capped at 100. Skip this section if you don't plan to fill in the report.)*

1. **Output check.** Run `./part3 "Hello iso world" 4 50` and confirm `output.txt` is clean. Paste 3 lines.
2. **The "why this scope" question.** Your Part 2 mutex and your Part 3 semaphore both wrap the entire `my_write` body. In **3–5 sentences**, explain *why each one is necessary*. Address: what would the corruption look like in Part 3 if you locked only the `write()` call instead of all of `my_write`? Be concrete — give an example interleaving in terms of bytes in the output file.
3. **Performance table.** Run all three configurations on **both** Part 2 and Part 3:

   | config | part2 elapsed_ms (median of 3) | part3 elapsed_ms (median of 3) |
   |---|---|---|
   | `"test" 1 1000`  | … | … |
   | `"test" 50 100`  | … | … |
   | `"test" 50 1000` | … | … |

   Then explain in 4–6 sentences:
   - Which is faster, and why?
   - How does spawn cost (`fork` vs `pthread_create`) factor in?
   - How does sync-primitive cost (in-process mutex vs kernel `semop` syscall) factor in?
   - At which configuration is each cost most visible?

## Acceptance Criteria
- Compiles cleanly with `-Wall -Wextra` (no warnings).
- Output is well-formed (same regex as Part 2); every `(ID, Seq)` exactly once; per-ID seqs are `0..writes_per_worker-1`.
- No deadlocks (generous timeout enforced).
- Semaphore removed via `IPC_RMID` — `ipcs -s` shows nothing after exit.
- All children are reaped.
- Stale-semaphore handling on `EEXIST` works.

## Forbidden in Part 3
- Threads (`pthread_*`). This part is processes-only.
- Mutexes (`pthread_mutex_*`).
- POSIX semaphores (`sem_open`, `sem_wait`, etc.) — this part is **System V** semaphores only.
- Lock files / `flock` / `fcntl(F_SETLK)`.
- Any form of `fopen`/`fprintf`/`puts`/etc. for `output.txt`.

---

# REPORT.md

# REPORT — Exercise 2 (Optional Bonus)

> Filling this out is **optional**. You can earn up to **+5 bonus points** on top of your code score (capped at 100 total).

**Name:**
**Student ID (5 digits):**
**Date:**

---

## 1. Buffer Logic

In your own words, describe how your `my_write` handles a string `str` that is **longer** than the remaining space in `buffer`. What happens when `str` is even longer than `CHUNK_SIZE` itself?

> *Your answer here.*

---

## 2. Part 1 — Observed Chaos

Run:
```
./part1 "Hello concurrent world" 4 50
```

### 2a. Excerpt
Paste 5–10 consecutive lines from `output.txt` that show interleaved or corrupted output (you may need a heavier load — e.g. `8 2000` — to see clear corruption depending on how many cores your machine has):

```
<paste here>
```

### 2b. Explanation
Explain *why* the corruption looks the way it does. Specifically address: where does `buffer` live in memory after `fork()`? Where does the file offset live? Which one is shared, and which one is duplicated?

> *Your answer here.*

---

## 3. Part 2 — Mutex Scope

### 3a. Could you make the lock narrower?
You're holding the mutex for the entire duration of `my_write`. Could you instead lock only the increment of `buffer_pos`, drop the lock, and then do the byte copy outside the lock? Explain — concretely — what would go wrong.

> *Your answer here.*

### 3b. CHUNK_SIZE Experiment
Run `./part2 "test" 50 1000` with three different values of `CHUNK_SIZE` (recompile each time):

| CHUNK_SIZE | elapsed_ms |
|---|---|
| 8    |  |
| 64   |  |
| 4096 |  |

Explain why timing changes the way it does. (Hint: think about the number of `write()` syscalls vs. the contention on the mutex.)

> *Your answer here.*

---

## 4. Part 3 — The Centerpiece Question

In Part 2 you locked the entire `my_write` with a mutex. In Part 3 you also lock the entire `my_write` — but with a named semaphore, **and** you must drain the buffer before releasing the lock.

### 4a. Why does the lock have to wrap the whole `my_write`?
Suppose you only locked the `write()` syscall in Part 3. Construct a concrete byte-level interleaving between two processes that produces a corrupted output line. Show what would end up in `output.txt`.

> *Your answer here.*

### 4b. Why drain the buffer before releasing the semaphore?
Even with the wide lock, you still have to flush leftover bytes before the final `semop` (the +1 release). Explain — again at the byte level — what goes wrong if you don't.

> *Your answer here.*

---

## 5. Performance Comparison: Threads+Mutex vs Processes+Semaphore

Run each configuration **three times** and report the median of `elapsed_ms`:

| config              | part2 (median ms) | part3 (median ms) |
|---|---|---|
| `"test" 1 1000`     |  |  |
| `"test" 50 100`     |  |  |
| `"test" 50 1000`    |  |  |

Address:
- Which is faster, and why?
- How does spawn cost (`fork` vs `pthread_create`) factor in?
- How does sync-primitive cost (in-process mutex vs kernel semaphore syscall) factor in?
- At which configuration is each cost most visible?

> *Your answer here.*
