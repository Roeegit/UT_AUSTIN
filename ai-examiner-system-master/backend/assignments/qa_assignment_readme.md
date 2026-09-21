# Assignment: Task Executor (taskexec)

## Overview

In this assignment you will build a **task executor** — a C program that reads a list of shell commands from an input file, runs each one in a separate child process, and logs the results to an output file.

This exercise practices: `fork()`, `exec()`, `pipe()`, `dup2()`, `waitpid()`, signal handling, and file I/O.

## Expected Files

You must submit the following files:

| File | Purpose |
|------|---------|
| `taskexec.c` | Main program: reads tasks, forks workers, collects results |
| `utils.c` | Helper functions: file parsing, logging, error reporting |
| `utils.h` | Header file for `utils.c` |

## Functional Requirements

### Input Format

The program receives two command-line arguments:

```
./taskexec <task_file> <log_file>
```

- `task_file`: a text file where each non-empty line is a shell command to execute (e.g., `ls -la /tmp`).
- `log_file`: path to the output log file (created/overwritten by your program).

Lines that are empty or start with `#` should be skipped.

Example `tasks.txt`:
```
ls -la /tmp
echo hello world
sleep 2
cat /etc/hostname
```

### Execution Model

1. **Parse** the task file and store all valid commands.
2. **For each command**, fork a child process:
   - The child must create a pipe and send a single "ready" byte (`'R'`) to the parent through the pipe **before** calling `execvp()`. This confirms the child is alive and about to exec.
   - The child redirects its `stdout` to a temporary file: `/tmp/taskexec_<pid>.out` (using `dup2()`).
   - The child then calls `execvp()` with the parsed command. If `execvp()` fails, the child must print an error to `stderr` and exit with status `1`.
3. **The parent** reads the "ready" byte from each child's pipe (with a 5-second timeout — if no byte arrives, log a warning and continue).
4. **After forking all children**, the parent calls `waitpid()` in a loop to collect all exit statuses.
5. **Log results** to `log_file`. Each line in the log must contain:
   ```
   [TASK <index>] Command: <command> | PID: <pid> | Exit: <status> | Signal: <signal_or_none>
   ```

### Signal Handling

- The parent must install a handler for `SIGINT` (Ctrl+C).
- On `SIGINT`, the parent must:
  1. Send `SIGTERM` to all living child processes.
  2. Wait for them to terminate (with a 3-second timeout before `SIGKILL`).
  3. Write a summary line to the log: `[INTERRUPTED] Killed <N> remaining tasks`.
  4. Close the log file and exit with status `2`.

### Error Handling

- If `task_file` cannot be opened: print to `stderr` and exit with status `1`.
- If `fork()` fails: log the failure for that task and continue with remaining tasks.
- If `log_file` cannot be created: print to `stderr` and exit with status `1`.
- All system calls (`pipe()`, `dup2()`, `fork()`, `open()`, etc.) must be checked for errors.

## Compilation

Your code must compile cleanly with:

```bash
gcc -Wall -Wextra -o taskexec taskexec.c utils.c
```

No warnings are permitted.

## Grading Criteria

- Correct multi-process execution (fork + exec)
- Proper pipe usage for child-parent communication
- Correct `dup2()` redirection
- Signal handling (SIGINT → graceful shutdown)
- Error handling on all system calls
- Clean code structure and separation between `taskexec.c` and `utils.c`
- No memory leaks, no zombie processes
