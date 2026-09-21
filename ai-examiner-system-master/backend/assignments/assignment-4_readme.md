[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/kZgdC9pR)
[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/REPLACE_ME)
# Exercise 4 — Inter-Process Communication: One Pipeline, Three Channels

## Due Date
30.06.2026

## Overview
You will solve the **same problem three times**, each time moving the data through a different inter-process communication (IPC) channel:

1. **Part 1 — Anonymous Pipe:** parent and child, connected by an unnamed kernel pipe.
2. **Part 2 — FIFO (named pipe):** the same stream, but through a *named* object that lives in the filesystem.
3. **Part 3 — Shared Memory:** the fastest channel — and the one where the kernel mediates *nothing*, so you build the synchronization protocol yourself.

Across all three parts the task is the same: a **producer** generates `N` numeric records and sends them to a **consumer**, which computes their `count`, `sum`, `min`, and `max`. What changes between parts — and what this assignment is really about — is the *channel* the data travels through. By the end you will understand:

- How an **anonymous pipe** (`pipe()` + `fork()`) connects related processes, and why each side must close the end it does not use (or the reader never sees EOF).
- How a **FIFO** (`mkfifo()`) is just a pipe with a name in the filesystem: it can connect unrelated processes, you can inspect its file type with `stat`/`lstat`, and — unlike a pipe — you must `unlink()` it yourself.
- How **shared memory** (`shmget`/`shmat`/`shmdt`/`shmctl`) gives you raw shared bytes with no flow control and no EOF, so the producer/consumer hand-shake is *your* responsibility.

## Repository Layout
```
.
├── README.md            — this file (read FIRST — contains the shared requirements)
├── Part1.md             — anonymous pipe
├── Part2.md             — FIFO (named pipe)
├── Part3.md             — shared memory
├── src/
│   ├── common.h         — shared helpers (data model, I/O loops) — provided
│   ├── part1.c          — your code (stub provided)
│   ├── part2.c          — your code (stub provided)
│   ├── part3.c          — your code (stub provided)
│   └── Makefile
└── tests/
    └── sanity.py        — sanity check; run before submitting
```

## How to Read This Assignment
1. Read this README **end to end** — the "Shared Requirements" through "Forbidden / Allowed" sections apply to all three parts.
2. Then read `Part1.md`, `Part2.md`, `Part3.md` in order.
3. Implement the parts in order. The three `partN.c` files are independent (each has its own `main`), but they share the same data model, output format, command-line interface, and error-handling rules. **Reuse your own code** between parts — only the channel layer should change. The helpers in `common.h` are there to make that easy.

## Build & Run
```bash
cd src
make                 # builds part1, part2, part3
./part1 1000 7       # 1000 records, seed 7, over an anonymous pipe
./part2 1000 7       # same, over a FIFO
./part3 1000 7       # same, over shared memory
```
Each part prints one summary line to **stdout** and a timing line to **stderr**:
```
[Channel: PIPE] count=1000 sum=49884500 min=2 max=99822
elapsed_ms=1.742
```

## Sanity Check
Before submitting, run:
```bash
python3 tests/sanity.py
```
This compiles your code and runs each part with small inputs, confirming the basics: it builds without warnings, the binaries run, each summary line is well-formed and numerically correct, the timing line is on stderr, and Part 3 does not leak a shared-memory segment.

**This is not a grader.** Passing it just means your code is not obviously broken — it doesn't guarantee a passing grade. Edge cases, stress loads, and forbidden-API checks happen separately during grading.

## Deliverables
Push to your GitHub Classroom repository before the deadline:
1. `id.txt` — a `.txt` file containing the last 5 digits of your ID.
2. `src/part1.c`, `src/part2.c`, `src/part3.c` — your three implementations.
3. `src/Makefile` — must build all three with `make`.

Do **not** commit binaries (`part1`, `part2`, `part3`). A `.gitignore` is provided.

---

# Shared Requirements

These apply to **all three parts**. Each `partN.c` is an independent file with its own `main()`, but the data model, output format, command-line interface, timing, and error-handling rules below are identical across all three. The only thing that differs between parts is the IPC channel.

## 1. The Data Model

A **producer** generates `N` records; record `i` (for `i = 0 .. N-1`) carries the value

```
value(i) = (i * 1103515245 + seed) mod 100000
```

computed in unsigned arithmetic. (This is a cheap, fully deterministic generator, so the grader can predict the aggregates for any `N` and `seed`.) `common.h` provides this as `value_at(i, seed)` — use it; do not invent your own formula.

The **consumer** receives the values and computes:

| Aggregate | Meaning |
|---|---|
| `count` | number of records received (must equal `N`) |
| `sum`   | sum of all values |
| `min`   | smallest value received |
| `max`   | largest value received |

Every record the producer sends must be received exactly once, in order. **No value may be lost, duplicated, or corrupted** — getting that right is the entire content of each part.

## 2. The Output Format (STRICT)

After the consumer has received all records, it prints **exactly one** line to **stdout**:

```
[Channel: <PIPE|FIFO|SHM>] count=<count> sum=<sum> min=<min> max=<max>
```

- `Channel` is the literal `PIPE` (Part 1), `FIFO` (Part 2), or `SHM` (Part 3), uppercase.
- `count`, `sum`, `min`, `max` are non-negative decimal integers printed with `%lu` / `%ld`.

Example:
```
[Channel: SHM] count=1000 sum=49884500 min=2 max=99822
```

The line is validated against this exact regex:
```
^\[Channel: (PIPE|FIFO|SHM)\] count=(\d+) sum=(\d+) min=(\d+) max=(\d+)\n$
```

> Note the exact spacing: one space after `Channel:`, single spaces between fields, single `\n` at the end. No trailing spaces, no `\t`.

## 3. Command-Line Arguments

Every part's `main()` must accept exactly:

```
./partN <N> <seed>
```

- `<N>` — a **positive** integer: how many records to send.
- `<seed>` — a **non-negative** integer: the generator seed.

If `argc != 3`, print
```
Usage: <argv[0]> <N> <seed>
```
to **stderr** and exit with status `1`. Reject a non-positive `N` or a negative `seed` with a clear error message to stderr and exit status `1`. (`common.h` provides `parse_args` that does exactly this.)

## 4. Timing

The process must:
1. Record a start timestamp **just before** creating the channel / spawning the worker, using `gettimeofday()` or `clock_gettime(CLOCK_MONOTONIC, …)`.
2. Record an end timestamp **just after** the consumer has finished and the channel has been cleaned up.
3. Print the elapsed wall-clock time in **milliseconds** to **`stderr`** (so it does not pollute the stdout summary):
   ```
   elapsed_ms=12.345
   ```
   The exact format is `elapsed_ms=<float>` with 3 decimal places.

## 5. Error Handling

Every system call (`pipe`, `fork`, `mkfifo`, `open`, `lstat`, `unlink`, `shmget`, `shmat`, `shmdt`, `shmctl`, `ftok`, `read`, `write`, `close`, `wait`/`waitpid`, …) must be checked. On failure, call `perror("<syscall-name>")` and exit with a non-zero status.

A "checked" call looks like this:
```c
pid_t pid = fork();
if (pid == -1) { perror("fork"); exit(1); }
```

Reads and writes on a pipe/FIFO may transfer **fewer bytes than requested**; you must loop until the whole record is transferred (the provided `write_all` / `read_full` helpers do this).

## 6. Cleanup

The program must leave the system in a clean state:

- Every file descriptor the program opens is closed before exit.
- Every child is reaped via `wait()` / `waitpid()` — **no zombies**.
- **Part 2:** the FIFO is removed with `unlink()`. After exit, the FIFO path must not exist.
- **Part 3:** the shared-memory segment is detached (`shmdt`) by every process that attached it and removed by the parent via `shmctl(shmid, IPC_RMID, NULL)`. After exit, `ipcs -m` must show no leftover segment.
- Children call `_exit(0)`, not `exit(0)`, to avoid running stdio cleanup in a forked copy.

---

## Forbidden / Allowed (Summary)

- ❌ Any third-party libraries.
- ❌ Sending the data through a regular file on disk (no `open("data.txt", …)` as the channel). Each part must use its assigned IPC mechanism.
- ❌ Mixing channels: no shared memory in Parts 1–2, no pipes/FIFOs in Part 3.
- ❌ `sleep`/`usleep` used as a *synchronization device* (i.e. "sleep long enough that the other side is surely done"). Real synchronization only.
- ✅ `printf`/`fprintf` for the summary line and the timing/error messages.
- ✅ The helpers in `common.h` (`value_at`, `write_all`, `read_full`, `tdiff_ms`, `parse_args`).
- ✅ Reusing your own aggregation code across the three parts.

## Submission Workflow (GitHub Classroom)
1. Accept the assignment via the Classroom link.
2. Clone your repository.
3. Implement, test locally with `python3 tests/sanity.py`, commit, and push.

Good luck — this is the last one. The task is the same in all three parts on purpose: keep your eye on **the channel**, because that is where the operating system actually lives.

---
---

# Per-Part Specifications

> The three part specs below (`Part1.md`, `Part2.md`, `Part3.md`) are part of the
> assignment and define the per-channel requirements the student's `src/partN.c`
> must satisfy. They are included here so the code review judges each file against
> its full specification.

---

# Part 1 — The Baseline (Anonymous Pipe)

## Objective
Move the record stream from a producer to a consumer through an **anonymous pipe**, the simplest IPC channel: an in-kernel FIFO byte buffer with no name, reachable only through inherited file descriptors.

## Architecture
1. The **parent** parses `argv`, records the start timestamp, and creates the pipe (`pipe(fd)`). `fd[0]` is the **read** end, `fd[1]` is the **write** end.
2. The parent `fork()`s once.
3. The **child** is the *producer*. It closes the read end it will not use, writes the `N` records (each record is one `long` value from `value_at`), then closes the write end and `_exit(0)`s.
4. The **parent** is the *consumer*. It closes the write end it will not use, reads records in a loop until `read` returns `0` (EOF), accumulating `count`/`sum`/`min`/`max`.
5. The parent reaps the child with `waitpid`, records the end timestamp, prints the summary to stdout and the timing to stderr.

## The One Rule You Must Not Forget: Close the Unused Ends
After `fork()`, **both** processes hold **both** ends of the pipe. A reader sees EOF (`read` returns `0`) only when **every** write end — in **every** process — has been closed. If the consumer keeps its own copy of the write end (`fd[1]`) open, `read` will **block forever**. Symmetrically, the producer should close `fd[0]` (the read end).

## Reading and Writing Whole Records
A single `read`/`write` from a pipe may move **fewer bytes than requested**. Loop until the full record is transferred — the provided `read_full` / `write_all` helpers do exactly this. `read_full` returns `0` precisely at a clean EOF on a record boundary, which is the consumer loop's exit condition.

## Workers Use `_exit`, Not `exit`
The child should call `_exit(0)`, **not** `exit(0)`, to avoid running `atexit` handlers and flushing inherited stdio buffers in the forked copy.

## Acceptance Criteria (Autograder)
- Compiles cleanly with `-Wall -Wextra` (no warnings).
- Exits with status `0` on valid input.
- Summary line matches the format regex (channel tag `PIPE`) and is numerically correct for the given `N`/`seed`.
- `elapsed_ms=…` is printed to stderr.
- Every `pipe`/`fork`/`read`/`write`/`close`/`waitpid` call is `perror`-checked.
- No zombies; both pipe ends closed before exit.

## Forbidden in Part 1
- FIFOs (`mkfifo`) or shared memory (`shmget`, …) — anonymous pipes only.
- Using a regular on-disk file as the channel.
- `sleep`/`usleep` as a synchronization device.

---

# Part 2 — Give the Pipe a Name (FIFO)

## Objective
Send the same record stream through a **FIFO** (a *named pipe*). A FIFO behaves like the Part 1 pipe — an ordered, lossless byte stream with blocking reads and an EOF — but it has a **name in the filesystem**: it could connect unrelated processes, and it does **not** clean itself up.

## Architecture
1. The **parent** parses `argv` and builds a unique FIFO path, e.g. `/tmp/os_ass4_fifo_<pid>` (PID keeps simultaneous runs from colliding). Call `unlink(fifo_path)` first (ignoring any error) to clear a stale leftover.
2. Create the FIFO with `mkfifo(fifo_path, 0644)` and record the start timestamp.
3. **Verify the file type from its inode** with `lstat` + `S_ISFIFO` (required — the assignment's hook into file-type/inode inspection).
4. `fork()` once. The **child** is the producer (`open` `O_WRONLY`, write `N` records, close); the **parent** is the consumer (`open` `O_RDONLY`, read until EOF, aggregate).
5. The parent reaps the child, **`unlink()`s the FIFO**, records the end timestamp, prints the summary and timing.

## The Open Handshake
Opening a FIFO blocks by design: `O_RDONLY` blocks until someone opens for writing, and `O_WRONLY` blocks until someone opens for reading. The child (`O_WRONLY`) and parent (`O_RDONLY`) unblock each other.

## Cleanup: A FIFO Does Not Free Itself
A FIFO has a name in the filesystem that persists until removed. The program must `unlink(fifo_path)`; after exit the path must not exist.

## Acceptance Criteria (Autograder)
- Compiles cleanly with `-Wall -Wextra` (no warnings).
- Summary line matches the format regex (channel tag `FIFO`) and is numerically correct.
- `elapsed_ms=…` is printed to stderr.
- The FIFO is created, verified with `lstat`/`S_ISFIFO`, and `unlink`ed — no leftover path after exit.
- Every system call is `perror`-checked; child is reaped; no zombies.

## Forbidden in Part 2
- Anonymous pipes (`pipe()`) or shared memory (`shmget`, …) — FIFOs only.
- Using a regular on-disk file as the channel.
- Leaving the FIFO behind (skipping `unlink`).
- `sleep`/`usleep` as a synchronization device.

---

# Part 3 — Raw Speed, Your Rules (Shared Memory)

## Objective
Send the same record stream through a **System V shared-memory segment** — the fastest channel (no syscall per access, no kernel copy) but with **no flow control and no EOF**. The producer/consumer hand-shake is entirely the student's responsibility.

## API
`ftok` (derive key from a stable path, e.g. `argv[0]`) → `shmget(key, size, IPC_CREAT | IPC_EXCL | 0644)` → `shmat` (returns `(void*)-1` on failure, not `NULL`) → use as memory → `shmdt` → `shmctl(shmid, IPC_RMID, NULL)`. A stale segment makes `shmget` with `IPC_EXCL` fail with `errno == EEXIST`: look up the existing id, remove it, and retry. An attachment made **before** `fork()` is inherited by the child.

## Architecture
1. The **parent** derives the key, creates the segment (with `EEXIST` recovery), and attaches it.
2. The shared region is a one-slot **mailbox**: `volatile int status` (`ST_EMPTY`/`ST_FULL`/`ST_DONE`) + `volatile long value`. Parent initializes `status = ST_EMPTY`, records start timestamp, and `fork()`s.
3. **Producer (child):** for each record, wait until slot is `EMPTY`, write the value, mark `FULL`. After the last record, wait until `EMPTY` again, then mark `DONE`. Detach and `_exit(0)`.
4. **Consumer (parent):** loop — wait until slot is not `EMPTY`; if `DONE`, stop; else read value, aggregate, mark `EMPTY`.
5. Parent reaps child, `shmdt`, `shmctl(... IPC_RMID)`, records end timestamp, prints summary and timing.

## The Synchronization You Have to Build Yourself
Strict **one-slot ping-pong**: producer writes only when `EMPTY`, consumer reads only when `FULL`, transitions signalled via `status`. Two failures to prevent: **lost update** (producer overwrites an unread value) and **torn/premature read** (consumer reads mid-write or stale). The **order** of writing `value` vs `status` (and reading them) matters — get it backwards and the torn-read race reopens.

### Two details that matter
- **`volatile`** on `status` **and** `value`, so each side sees the other process's updates (the compiler must not cache in a register).
- **`sched_yield()`** in the busy-wait instead of a bare spin, to avoid pinning a CPU at 100%. (A fixed `sleep`/`usleep` as synchronization is forbidden; `sched_yield` is allowed and encouraged.)

## Acceptance Criteria (Autograder)
- Compiles cleanly with `-Wall -Wextra` (no warnings).
- Summary line matches the format regex (channel tag `SHM`) and is numerically correct — **including under repeated/stress runs** (a broken hand-shake shows up as a wrong `sum`).
- `elapsed_ms=…` is printed to stderr.
- Segment removed via `IPC_RMID` — `ipcs -m` shows nothing after exit.
- Stale-segment handling on `EEXIST` works.
- Child is reaped; both sides `shmdt`; no zombies.

## Forbidden in Part 3
- Pipes (`pipe()`) or FIFOs (`mkfifo()`) — shared memory only.
- Using a regular on-disk file as the channel.
- `sleep`/`usleep` as a synchronization device (`sched_yield()` is allowed).

---

# Provided Helpers (`src/common.h`) — for reference, not graded

The following helper header is provided to all students. The student's `partN.c`
files are expected to use these helpers (`value_at`, `write_all`, `read_full`,
`tdiff_ms`, `parse_args`) rather than reinvent them. It is shown here so the review
can judge whether the student used the provided API correctly; `common.h` itself is
not student-authored and is not part of the grade.

```c
/* Deterministic value for record i. */
static inline long value_at(long i, long seed) {
    return (long)(((unsigned long)i * 1103515245UL + (unsigned long)seed) % 100000UL);
}

/* Write exactly n bytes, looping over short writes. */
static inline void write_all(int fd, const void *buf, size_t n);

/* Read exactly n bytes. Returns 1 on success, 0 on a clean EOF at a record
   boundary, and aborts on an EOF in the middle of a record. */
static inline int read_full(int fd, void *buf, size_t n);

/* Elapsed milliseconds between two timevals. */
static inline double tdiff_ms(struct timeval a, struct timeval b);

/* Parse "<N> <seed>" from argv into *N and *seed. Returns 0 on success, -1 on
   bad usage (argc != 3, N <= 0, or seed < 0), printing the usage/error to stderr. */
static inline int parse_args(int argc, char *argv[], long *N, long *seed);
```
