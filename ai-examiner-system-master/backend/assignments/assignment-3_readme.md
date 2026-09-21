# OS Course 2026 — Exercise 3: Signals, CPU Scheduling, and Synchronization

| | |
|---|---|
| **Deadline** | 11.6.2026, 23:59. |
| **Submission** | GitHub Classroom — push your completed template files (`ex3.c`, `Focus-Mode.c`, `CPU-Scheduler.c`) to your repository |
| **Type** | Solo assignment |
| **Language** | C only |
| **TA** | Einat Noyman |
| **Questions** | Course forum: https://lemida.biu.ac.il/mod/forum/view.php?id=3093532 |
| **Deadline extensions** | Email os.biu.2026@gmail.com (see details below) |

> **⚠️ Please read ALL instructions carefully before starting to code.**

> **Can't find your name in the GitHub Classroom?** If you don't see your name on the exercise classroom welcome board, contact us immediately for help.

### 📋 Implementation & Submission Details

To complete this assignment, you must implement your code using the provided template files in your repository:
* **`Focus-Mode.c`**: Contains the logic and implementation for the Warmup section.
* **`CPU-Scheduler.c`**: Contains the logic and implementation for the Main Part scheduling engine.
* **`ex3.c`**: The main entry point that validates command-line arguments and routes execution to either the Focus Mode simulator or the CPU Scheduler based on your input.

**Submission:** Submit the assignment by pushing your finalized versions of these three files to your personal GitHub Classroom repository. 

**⚠️ Important Note on Automated Testing:** Please note that **there are no automated tests running on the remote repository for this assignment.** Pushing to GitHub serves as your final submission but will not provide automatic feedback or grading. 

To verify your implementation's correctness, you should run tests locally using the provided inputs and expected output files found in the **`Focus-Mode-Tests`** and **`CPU-Scheduler-Tests`** folders. Keep in mind that these are simple, basic-usage examples to help you check your formatting and initial logic; they do not cover all edge cases and do not solely determine your final grade. You are highly encouraged to write your own tests to thoroughly validate your code!

---

### Deadline extensions

If you need extra time, email **os.biu.2026@gmail.com** with:
- Your **GitHub username**
- How many **extra days** you are requesting
- A brief reason

Don't worry — we are nice. If you have a good reason, you will get the extension. **Requests not answered by 2 days before the submission date are automatically accepted.**

### Questions and help

We strongly encourage you to ask questions on the course forum: https://lemida.biu.ac.il/mod/forum/view.php?id=3093532

Help each other! If you see a question you can answer, go ahead. We will make sure every question gets answered.

---

## Exercise Instructions

This exercise focuses on **signals**. You may use any related material discussed in class up to and including Practical Session 8 that you find helpful.

## 🎯 WARMUP: Focus Mode Simulator (20% of the grade)

To kick things off, you'll build a simple simulation that helps you practice Unix signal handling and masking. This simulator models a scenario where a student tries to stay focused while different distractions attempt to interrupt them.
You can read more about this great time management technique [here](https://www.intelligentchange.com/blogs/read/focus-time-technique).

### 🚀 Overview

You will implement a **Focus Mode Simulator** that:

* Lets a user simulate rounds of focused work.
* Uses **Unix signals** to simulate incoming **distractions**.
* **Blocks signals** during each focus round.
* At the end of the round, **checks for pending signals**, unblocks them, and handles them one by one.
* Displays a corresponding **outcome** for each distraction.

This will help you become familiar with:

* Signal registration (`sigaction`)
* Signal blocking/unblocking (`sigprocmask`)
* Handling pending signals (`sigpending`, `sigismember`)
* Designing signal-based event logic in C

### 🔧 How it Works

Your simulator will support exactly **3 types of distractions**:

1. **Email notification** — Simulate an academic announcement

   Message after handling:
   `"[Outcome:] The TA announced: Everyone get 100 on the exercise!"`

2. **Reminder to pick up delivery** — Simulate a timed reminder

   Message after handling:
   `"[Outcome:] You picked it up just in time."`

3. **Doorbell ringing** — Simulate a food delivery

   Message after handling:
   `"[Outcome:] Food delivery is here."`

**Invalid input:** If the user enters anything other than `1`, `2`, `3`, or `q`, simply ignore it — it still counts as one iteration of the round.

If the user enters `q`, the current round should end immediately, and the program should proceed to check pending distractions and then continue to the next round without waiting for the remaining inputs.

At the end of each round, display any pending distractions and their corresponding outcomes in the specified format shown below. They should be listed in the same order as defined above (1, 2, 3), without duplicates — as we discussed in class, identical signals are not queued.

If **no distractions** were triggered during a round, display: `No distractions reached you this round.`

🛠️ You may **choose any 3 Unix signals** (except `SIGKILL` or `SIGSTOP`, of course) to simulate each of these distractions, just ensure to stay consistent!

### 🔌 Program Execution

As mentioned, `ex3.c` is expected to behave differently based on the **first argument** passed to it.

If the **first argument is** `"Focus-Mode"` (case-sensitive), then the **next two arguments must be provided** and must be **positive integers**:

1. **Number of Focus Rounds** — how many focus rounds to run.
2. **Duration of Each Round** — how many input cycles occur per round.

For example, to compile and run the program in **Focus Mode** for **5 rounds**, each with **3 iterations**, run:

```bash
gcc ex3.c -o ex3
./ex3 Focus-Mode 5 3
```
Here:

* `"Focus-Mode"` selects the focus simulation mode.
* `5` means 5 rounds of focus mode.
* `3` means 3 input prompts per round.

### ⚠️ Arguments Validation:

If the program is run with insufficient arguments (fewer than 4), or if the first argument is neither `Focus-Mode` nor `CPU-Scheduler`, it should display the following usage message and exit:

```c
printf("Usage: %s <Focus-Mode/CPU-Scheduler> <Num-Of-Rounds/Processes.csv> <Round-Duration/Time-Quantum>", argv[0]);
```

You **don't need to deeply validate** the argument values (like checking if they're numeric) — just check that:

* The argument count is correct (exactly 4, including the program name)
* The first argument is either `"Focus-Mode"` or `"CPU-Scheduler"` (case-sensitive). The rest is assumed to be correct.

**Use the provided `ex3.c`, `Focus-Mode.c`, `CPU-Scheduler.c` templates as a starting point.**

### 🖨️ Expected Output Format

Let's walk through the previous example: running 5 rounds with 3 iterations each.

The user input shown below is enclosed in double asterisks (**):

```text
Entering Focus Mode. All distractions are blocked.
══════════════════════════════════════════════
                Focus Round 1                
──────────────────────────────────────────────

Simulate a distraction:
  1 = Email notification
  2 = Reminder to pick up delivery
  3 = Doorbell Ringing
  q = Quit
>> **1**

Simulate a distraction:
  1 = Email notification
  2 = Reminder to pick up delivery
  3 = Doorbell Ringing
  q = Quit
>> **2**

Simulate a distraction:
  1 = Email notification
  2 = Reminder to pick up delivery
  3 = Doorbell Ringing
  q = Quit
>> **3**
──────────────────────────────────────────────
        Checking pending distractions...      
──────────────────────────────────────────────
 - Email notification is waiting.
[Outcome:] The TA announced: Everyone get 100 on the exercise!
 - You have a reminder to pick up your delivery.
[Outcome:] You picked it up just in time.
 - The doorbell is ringing.
[Outcome:] Food delivery is here.
──────────────────────────────────────────────
             Back to Focus Mode.              
══════════════════════════════════════════════
══════════════════════════════════════════════
                Focus Round 2
──────────────────────────────────────────────

Simulate a distraction:
  1 = Email notification
  2 = Reminder to pick up delivery
  3 = Doorbell Ringing
  q = Quit
>> **3**

Simulate a distraction:
  1 = Email notification
  2 = Reminder to pick up delivery
  3 = Doorbell Ringing
  q = Quit
>> **2**

Simulate a distraction:
  1 = Email notification
  2 = Reminder to pick up delivery
  3 = Doorbell Ringing
  q = Quit
>> **1**
──────────────────────────────────────────────
        Checking pending distractions...      
──────────────────────────────────────────────
 - Email notification is waiting.
[Outcome:] The TA announced: Everyone get 100 on the exercise!
 - You have a reminder to pick up your delivery.
[Outcome:] You picked it up just in time.
 - The doorbell is ringing.
[Outcome:] Food delivery is here.
──────────────────────────────────────────────
             Back to Focus Mode.              
══════════════════════════════════════════════
══════════════════════════════════════════════
                Focus Round 3
──────────────────────────────────────────────

Simulate a distraction:
  1 = Email notification
  2 = Reminder to pick up delivery
  3 = Doorbell Ringing
  q = Quit
>> **1**

Simulate a distraction:
  1 = Email notification
  2 = Reminder to pick up delivery
  3 = Doorbell Ringing
  q = Quit
>> **1**

Simulate a distraction:
  1 = Email notification
  2 = Reminder to pick up delivery
  3 = Doorbell Ringing
  q = Quit
>> **1**
──────────────────────────────────────────────
        Checking pending distractions...      
──────────────────────────────────────────────
 - Email notification is waiting.
[Outcome:] The TA announced: Everyone get 100 on the exercise!
──────────────────────────────────────────────
             Back to Focus Mode.              
══════════════════════════════════════════════
══════════════════════════════════════════════
                Focus Round 4
──────────────────────────────────────────────

Simulate a distraction:
  1 = Email notification
  2 = Reminder to pick up delivery
  3 = Doorbell Ringing
  q = Quit
>> **2**

Simulate a distraction:
  1 = Email notification
  2 = Reminder to pick up delivery
  3 = Doorbell Ringing
  q = Quit
>> **q**
──────────────────────────────────────────────
        Checking pending distractions...      
──────────────────────────────────────────────
 - You have a reminder to pick up your delivery.
[Outcome:] You picked it up just in time.
──────────────────────────────────────────────
             Back to Focus Mode.              
══════════════════════════════════════════════
══════════════════════════════════════════════
                Focus Round 5
──────────────────────────────────────────────

Simulate a distraction:
  1 = Email notification
  2 = Reminder to pick up delivery
  3 = Doorbell Ringing
  q = Quit
>> **q**
──────────────────────────────────────────────
        Checking pending distractions...      
──────────────────────────────────────────────
No distractions reached you this round.
──────────────────────────────────────────────
             Back to Focus Mode.              
══════════════════════════════════════════════

Focus Mode complete. All distractions are now unblocked.
```

### 🧪 Testing and Debugging

We've included 3 inputs and expected output files in the "Focus-Mode-Tests" folder for your convenience — feel free to use them to test and debug your implementation.

### ⚠️ Pay Attention!

Submissions must use all of the following methods: `sigaction`, `sigprocmask`, `sigpending`, and `sigismember` in this part.
Any submission that doesn't will receive **zero points, no exceptions**.

---

🎯 Great job staying focused!
> Now that you've mastered your signal skills and are ready for a real _focus round_, it's time to level up and dive into the main part of the exercise: the **CPU Scheduler!**
> Take a deep breath, _block out all distractions_, and let's get started!

---

## 🖥️ MAIN PART: CPU Scheduler (80% of the grade)

You'll be building a lightweight "OS kernel" that reads a list of processes from a CSV file and schedules them according to the four classic algorithms covered in class. Throughout the project, you'll put into practice key concepts like:

* `fork()` to create child processes (**DO NOT** use threads — we'll cover those in the next exercise!)
* `kill()` and `sigaction()` or `signal()` to communicate with them
* `alarm()` and `pause()` to simulate time and control execution
* `sigprocmask()` to manage signal blocking

This is your chance to bring theory to life — simulating real CPU scheduling using the tools of the Unix world.

### 🚀 Overview

Your job is to implement a CPU scheduling engine that:

- Reads a list of processes from a CSV file.
- Simulates execution using signals and alarms.
- Displays a detailed execution timeline for each process using the FCFS, SJF, Priority (all in non-preemptive mode for simplicity) and Round Robin [scheduling algorithms](https://en.wikipedia.org/wiki/Scheduling_(computing)).
- **Runs all four algorithms sequentially** on the same process data, in this order: FCFS → SJF → Priority → Round Robin.

### 🔧 How it Works

* Each line in the input CSV file represents a **single process** and follows this format:

  ```csv
  Name,Description,Arrival Time,Burst Time,Priority
  ```

  - The fields are **comma-separated** and should appear in the specified order.
  - `Arrival Time`, `Burst Time`, and `Priority` are **integers** representing **time in seconds**.
  - `Burst Time` and `Priority` must be positive values.
  - `Arrival Time` may be 0 or any non-negative integer.
  - The `Name` field will not exceed 50 characters, and the `Description` field will not exceed 100 characters.
  - You can assume that the file format is valid and correctly structured.
  - You may assume there will be no more than 1000 processes, and each row in the CSV file will contain no more than 256 characters.
  - The CSV file does **not** have a header row — every line is a process.

* **Before scheduling**, sort all processes by their arrival time. If two processes have the same arrival time, preserve their original order from the CSV file (stable sort).

* Your program reads these processes and **simulates execution** of them according to each scheduling algorithm.

* To simulate the execution time of each process, use the `alarm` system call with the process's burst time. This will pause the process for the specified duration, effectively mimicking actual CPU work.

* Use `alarm` similarly to simulate idle time when no processes are ready to run — representing the CPU waiting for the next arrival.

* The simulation should be **fully deterministic**, reflecting the logic of a real OS-level scheduler.

* **Tie-breaking rule:** If two or more processes have the same values for the fields used to determine their order (based on the current scheduling algorithm), then you should preserve their original order as they appear in the input CSV file.

* At the end of each scheduling algorithm, display a final report summarizing its results:
  - For the **FCFS, SJF, and Priority** algorithms, include the **average waiting time**, formatted to two digits after the decimal point.
  - For the **Round Robin** algorithm, display the **total turnaround time** — the total elapsed time from the start of scheduling until the last process completes.


### 📊 Key Definitions

- **Waiting Time** (per process): The time a process spends waiting in the ready queue before it starts executing. For non-preemptive algorithms: `Waiting Time = Start Time - Arrival Time`. Idle time (when no process is ready) does **not** count as waiting time for any process.
- **Average Waiting Time**: The sum of all individual waiting times divided by the total number of processes.
- **Total Turnaround Time** (Round Robin): The total elapsed time from time 0 until the last process finishes execution.

### 🧠 Scheduling Algorithms to Implement

1. **FCFS** – First Come, First Served: Processes are scheduled in order of their arrival time.
2. **SJF** – Shortest Job First: Among all processes that have arrived and are waiting, the one with the shortest burst time runs next.
3. **Priority Scheduling** – Among all processes that have arrived and are waiting, the one with the lowest priority number runs next (lower number = higher priority).
4. **Round Robin** – Processes are scheduled in arrival order using a fixed time quantum (from CLI argument). Each process runs for at most `time_quantum` seconds per turn. If a process's remaining burst time is less than the time quantum, it runs for only its remaining time. When a process's quantum expires and it still has remaining work, it goes back to the end of the ready queue.

  Note: The first three algorithms are implemented in **non-preemptive** mode — once a process starts running, it runs to completion.

### 🔌 Program Execution

If the **first argument is** `"CPU-Scheduler"` (case-sensitive), then the **next two arguments must be provided** as follows:

1. **The path to the CSV file** containing the list of processes.
2. **The time quantum** (in seconds) to be used *only* for the **Round Robin** scheduling algorithm.

For example, to compile and run your program with a CSV file and a time quantum of 2:

```bash
gcc ex3.c -o ex3
./ex3 CPU-Scheduler processes.csv 2
```

Where:

* `CPU-Scheduler` selects the CPU scheduling mode.
* `processes.csv` is the file in the current directory containing the process list.
* `2` is the time quantum used *only* for the Round Robin part of the simulation.

Use the same arguments validation as described in the warmup part.

### 🖨️ Expected Output Format

Let's walk through an example using the following `processes.csv` file:

```csv
P1,System Bootloader,0,3,5
P2,Kernel Initialization,5,4,4
P3,Device Driver Loading,4,4,1
P4,Network Services Startup,4,1,2
```

Assuming you compile and run your program as follows:

```bash
./ex3 CPU-Scheduler processes.csv 2
```

Your program should display a well-formatted output **for each scheduling algorithm** in the following style:

```text
══════════════════════════════════════════════
>> Scheduler Mode : FCFS
>> Engine Status  : Initialized
──────────────────────────────────────────────

0 → 3: P1 Running System Bootloader.
3 → 4: Idle.
4 → 8: P3 Running Device Driver Loading.
8 → 9: P4 Running Network Services Startup.
9 → 13: P2 Running Kernel Initialization.

──────────────────────────────────────────────
>> Engine Status  : Completed
>> Summary        :
   └─ Average Waiting Time : 2.00 time units
>> End of Report
══════════════════════════════════════════════

══════════════════════════════════════════════
>> Scheduler Mode : SJF
>> Engine Status  : Initialized
──────────────────────────────────────────────

0 → 3: P1 Running System Bootloader.
3 → 4: Idle.
4 → 5: P4 Running Network Services Startup.
5 → 9: P3 Running Device Driver Loading.
9 → 13: P2 Running Kernel Initialization.

──────────────────────────────────────────────
>> Engine Status  : Completed
>> Summary        :
   └─ Average Waiting Time : 1.25 time units
>> End of Report
══════════════════════════════════════════════

══════════════════════════════════════════════
>> Scheduler Mode : Priority
>> Engine Status  : Initialized
──────────────────────────────────────────────

0 → 3: P1 Running System Bootloader.
3 → 4: Idle.
4 → 8: P3 Running Device Driver Loading.
8 → 9: P4 Running Network Services Startup.
9 → 13: P2 Running Kernel Initialization.

──────────────────────────────────────────────
>> Engine Status  : Completed
>> Summary        :
   └─ Average Waiting Time : 2.00 time units
>> End of Report
══════════════════════════════════════════════

══════════════════════════════════════════════
>> Scheduler Mode : Round Robin
>> Engine Status  : Initialized
──────────────────────────────────────────────

0 → 2: P1 Running System Bootloader.
2 → 3: P1 Running System Bootloader.
3 → 4: Idle.
4 → 6: P3 Running Device Driver Loading.
6 → 7: P4 Running Network Services Startup.
7 → 9: P2 Running Kernel Initialization.
9 → 11: P3 Running Device Driver Loading.
11 → 13: P2 Running Kernel Initialization.

──────────────────────────────────────────────
>> Engine Status  : Completed
>> Summary        :
   └─ Total Turnaround Time : 13 time units

>> End of Report
══════════════════════════════════════════════
```

**Output format notes:**
- Each timeline entry follows the format: `START → END: PROCESS_NAME Running DESCRIPTION.`
- Idle periods follow the format: `START → END: Idle.`
- In Round Robin, when a process resumes after being preempted, it shows the same "Running DESCRIPTION." message again.
- There is one blank line after the last timeline entry before the separator line.

Here is a demonstration video showcasing how your final execution should appear, including its speed, behavior, and timing of delays:

https://github.com/user-attachments/assets/4774f31b-bf7c-4a0d-ac5e-d8fc764cb5a1

### 🧪 Testing and Debugging

We've included 5 sample CSV files along with their expected outputs in the "CPU-Scheduler-Tests" folder for your convenience — feel free to use them to test and debug your implementation.
Of course, these examples don't cover every possible scenario, so be sure to test your code thoroughly before submitting.
Think creatively about edge cases and interesting or unusual behaviors your scheduler might encounter!

### ⚠️ Pay Attention!

Submissions must use at least one of the following methods: `signal`, `sigaction`, `sigprocmask`, `sigpending`, and `sigismember` in this part.
Any submission that doesn't will receive **zero points, no exceptions**.

---

## 📌 Tips and Hints

* Take time to plan your structure, flow and approach before diving into the code — it will save you time and prevent unnecessary headaches later!
* Be mindful of synchronization and race conditions, and address them to ensure deterministic output on every execution
* Modularize your code: parsing, scheduling logic, simulation, output formatting
* Coordinate child processes using `SIGSTOP`/`SIGCONT` signals to pause/resume
* Consider using a real-time signal like [`SIGRTMIN`](https://dougsland.livejournal.com/43885.html) for more reliable and precise synchronization between processes
* Prefer using `sigaction` over the simpler `signal` function for more robust and reliable signal handling
* It's recommended to use `write` rather than [`printf`](https://unix.stackexchange.com/questions/609210/why-printf-is-not-asyc-signal-safe-function?utm_source=chatgpt.com) for output operations as it's [async-signal-safe](https://docs.oracle.com/cd/E19455-01/806-5257/gen-26/index.html?utm_source=chatgpt.com)
* Measure **Waiting Time** and **Turnaround Time** carefully — refer to the definitions above


💪🏻 Happy coding, and may your waiting times be minimal!
