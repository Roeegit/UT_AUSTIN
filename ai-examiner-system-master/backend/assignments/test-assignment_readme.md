# Exercise 2: Operating Systems

## Due Date
The due date for this exercise is **18.5.2025, 23:59**.

## Submission Instructions
Submit your solution as a zip file containing **ONLY** the following files:
- `tournament.c`
- `gladiator.c`
- `backup.c`
- `file_processor.c`

### Submission Link
Please submit your zip file to the submission system: [https://submit.cs.biu.ac.il/cgi-bin/welcome.cgi](https://submit.cs.biu.ac.il/cgi-bin/welcome.cgi)

## Exercise Instructions
This exercise consists of three parts. Please read the following files for detailed instructions:


# Gladiator Tournament

## Introduction

In this assignment, you are tasked with implementing a tournament between gladiators. Each gladiator is represented as a process, and their fight is executed in a series of forked child processes. The tournament will declare the winner based on the last gladiator standing after the sequence of battles.

The project will use various system calls and concepts, including `fork()`, `exec()`, `wait()`, file descriptors, and process management, to simulate the tournament. Additionally, you'll be working with logging to file, where each gladiator logs their actions, health, and attack values.

## How is this gonna work

**Tournament Progression**:
1. The `tournament.c` program starts by forking four gladiators.
2. Each gladiator’s process is executed with `exec()`, running the `gladiator.c` program.
3. Each gladiator fights their opponents in order, deducting health as they go.
4. Once a gladiator’s health reaches zero or below, they "fall" and stop fighting.
5. The `tournament.c` program waits for all gladiators to finish with `wait()` or `waitpid()` and declares the winner based on the last gladiator standing.

![it took me 1 hour to make](image.png)
## Task Overview

### 1. Tournament Setup

The tournament consists of four gladiators. Each gladiator has a file describing their initial stats and the opponents they will fight in order. You will write a `tournament.c` program that will:
- Define the gladiators and their matching files:
```c
char* gladiator_names[NUM_GLADIATORS] = {"Maximus", "Lucius", "Commodus", "Spartacus"};
char* gladiator_files[NUM_GLADIATORS] = {"G1", "G2", "G3", "G4"};
```
- Fork four child processes (one for each gladiator).
- Use `exec()` to launch each gladiator as a separate process with the `gladiator` executable.
    > **Tip:** Pass the matching gladiator file name as an argument :)
- Wait for all child processes to complete using `wait()` or `waitpid()`.
- Determine the winner based on the gladiator who remains alive last, i.e., the one whose process terminates last.

### 2. Gladiator Stats

Each gladiator is represented by a text file (`G1.txt`, `G2.txt`, etc.) that contains their stats:

```
Health, Attack, Opponent1, Opponent2, Opponent3
```

Where:
- `Health` is the gladiator's starting health.
- `Attack` is the gladiator's attack power.
- `Opponent1`, `Opponent2`, and `Opponent3` represent the gladiators that this gladiator will fight in sequence.

The gladiator will attack each opponent in the specified order, deducting the opponent's attack power from the gladiator's health until it reaches zero or below.

- **Example**:
    ```
    1500, 100, 3, 2, 4
    ```

    Where:
    - `1500` is the gladiator’s health.
    - `100` is the gladiator’s attack power.
    - `3, 2, 4` represent the gladiators he will fight (i.e., gladiator 3 first, gladiator 2 second, and gladiator 4 last - and loop over it until he dies).

### 3. Gladiator Fight Simulation

Each gladiator will:
- Read their stats from their respective file (`Maximus => G1.txt`, `Lucius  => G2.txt`, etc.).
- Fight the three opponents in the order specified in the file.
- Deduct its self health based on the opponent's attack power.
- Log their actions and health status into a log file (`G1_log.txt`, `G2_log.txt`, etc.).
- Keep fighting (in the same order) until health is not positive.
- After a battle (when health is not positive), the process will exit with status 0.

### 4. Logging and Quotes

For a more dramatic effect, each gladiator's log file should contain:
- A record of each fight with the opponent's attack power and the gladiator's remaining health.
- A final message when the gladiator is defeated.

Each gladiator's log should look like:

```
Gladiator process started. 1234: 
Facing opponent 3... Taking 90 damage
Are you not entertained? Remaining health: 1410
Facing opponent 2... Taking 100 damage
Are you not entertained? Remaining health: 1310
Facing opponent 4... Taking 110 damage
Are you not entertained? Remaining health: 1200
...
...
Facing opponent 3... Taking 90 damage
Are you not entertained? Remaining health: 70
Facing opponent 2... Taking 100 damage
The gladiator has fallen... Final health: -30
```
> **Note**:  
> **MAKE SURE THAT THE LOG FILE IS CREATED WITH THE RIGHT DATA, IT WILL BE CHECKED**

### 5. Determining the Winner

The winner is determined based on the last gladiator who remains alive. This will be the gladiator whose process exits last. The tournament program will print the winner’s name in the following format:

```
The gods have spoken, the winner of the tournament is [gladiator_name]!
```
> The winner message might not be deterministic. If we decide to check it, we'll choose numbers that guarantee a deterministic outcome (like 1300000 health...)

## Running example
```sh
omer@Omer:~/uni/os/targilim/2025B/ex2/part1$ gcc -o tournament tournament.c
omer@Omer:~/uni/os/targilim/2025B/ex2/part1$ gcc -o gladiator gladiator.c
omer@Omer:~/uni/os/targilim/2025B/ex2/part1$ ./tournament
The gods have spoken, the winner of the tournament is Lucius!
```

## Submission Guidelines

- Submit **only** this following files:
  1. `tournament.c`: The main tournament program.
  2. `gladiator.c`: The gladiator simulation program.

## More things & hints
- You don't need at any point of this assignment to write to the G{i}.txt files.
- **You must name the gladiator executable `gladiator` and call it via exec**.
- Use `fork()` to create child processes for each gladiator.
- Use `exec()` to execute the gladiator fight program (`gladiator.c`) in each child process, you cant use `system()`.
- Use `waitpid()` or `wait()` to wait for each gladiator to finish their fight.
- Make sure the tournament program waits for all processes to complete before declaring the winner.
- Ensure that each gladiator's log file is created and updated during the battle.


## To Make Your Life Easier
- I recommend using `fscanf` for parsing the `G_{i}.txt` files (in the `gladiator.c` file)
- Example for inserting data into the log files (in the `gladiator.c` file):
```c
//print here the pid as I mentioned
while (health > 0) {
    for (int i = 0; i < 3; i++) {
        int opponent_attack = get_opponent_attack(opponents[i]);
        fprintf(logFile, "Facing opponent %d... Taking %d damage\n", opponents[i], opponent_attack);
        health -= opponent_attack;
        if (health > 0) {
            fprintf(logFile, "Are you not entertained? Remaining health: %d\n", health);
        } else {
            fprintf(logFile, "The gladiator has fallen... Final health: %d\n", health);
            break;
        }
    }
}
```
---

Good luck!

# File Processing System

This program processes read and write requests from a file (i.e `requests.txt`) and modifies a data file (i.e `data.txt`) accordingly. The implementation ensures that writes insert data **without overwriting existing content** and reads retrieve the correct portion of the file.

---

## Features
- **Reads specific ranges** from `data.txt` and saves the result to `read_results.txt`.
- **Writes new data at a given offset** while preserving the rest of the file.
- **Processes requests from input file** instead of user input.
- **Handles edge cases** such as invalid offsets and maintaining file integrity.
- **Ensures data persistence** with proper file operations (`lseek`, `read`, `write`).

---

## Files
### 1. First argument to your program, I'll call it the "data file"
Contains the initial data to be modified. This file starts with up to 256-bytes mix of uppercase letters, lowercase letters, and numbers.

Example:
```
ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdefghijklmnopqrstuvwxyz
```

### 2. Second argument to your program, I'll call it the "requests file"
Contains a series of read (`R`), write (`W`), and quit (`Q`) commands.

#### **Format**
```
R <start_offset> <end_offset>
W <offset> <text>
Q
```
- **`R` (Read):** Reads from `data.txt` between `start_offset` and `end_offset`, inclusive.
- **`W` (Write):** Writes `<text>` at `offset` (see the examples), shifting existing data forward.
- **`Q` (Quit):** Stops processing requests.

### 3. read_results.txt
Contains the output from the read commands, with new line between every read.


## How to Run The program
```bash
omer@Omer:~/uni/os/targilim/2025B/ex2/part2$ gcc -o file_processor file_processor.c
omer@Omer:~/uni/os/targilim/2025B/ex2/part2$ ./file_processor data.txt requests.txt
```

---

## Example Execution
### **Before Running** (`data.txt`)
```
1234567890

```

### **Requests (`requests.txt`)**
```
R 2 7
W 70 THISWOULDNTSHOWUP
R 0 25
W 5 OMEROMER
W 10 ILOVEOS
R 5 20
Q
```

### **Output**
*Its not important what is the output, only the files will be checked*

### **After Running (`data.txt`)**
```
12345OMEROILOVEOSMER67890

```
### **After Running (`read_results.txt`)**
```
345678
OMEROILOVEOSMER6

```

---

## Edge Cases Handled
✅ **Reading beyond file size** → Prevent it with boundary checks, and continue to the next line (dont exit).  
✅ **Writing beyond file size** → Same as reading, **if I give you the offset of the end of the file it's ok (but after that it's not)**
    **so is offset 0 (but before that it's not).**  
✅ **Other things** → You dont need to worry about integer overflow and `start > end` in the reading.

---

## Notes
- `data.txt` and `requests.txt` must exist, otherwise `perror("data.txt")` or `perror("requests.txt")`.
- Open `read_results.txt` with O_TRUNC and O_CREAT.
- The program modifies `data.txt` permanently, so keep backups if needed.

---



# Backup Tool

## Overview
This project is a **Backup Tool** that recursively copies a directory and its contents while preserving **symlinks** and **file permissions**. Instead of copying the actual content of regular files, the tool creates **hard links** to maintain storage efficiency.

## Features
- Recursively copies all files and directories.
- **Preserves symbolic links** (does not copy the actual file but recreates the symlink).
- **Creates hard links** instead of duplicating file content (for regular files).
- **Maintains file permissions** and attributes.

## How It Works
- The tool scans the given directory.
- If an item is:
  - A **regular file** → Creates a **hard link** in the backup location.
  - A **symbolic link** → Replicates the symlink (not the actual file).
  - A **directory** → Creates the same directory structure in the backup.
- The backup maintains the same structure as the original directory.

## Usage
### Compilation
```sh
gcc -o backup backup.c
```

### Running the Backup Tool
```sh
./backup <source_directory> <backup_directory>
```
Example:
```sh
./backup /home/omer/Documents /home/omer/Backup
```
> **Note**:  
> **You can get the full path like '/home/omer/Documents' or 'Documents' if we run it in '/home/omer/'.**
> **This should not affect your solution, but just clarifying :)**

## Example
```sh
omer@Omer:~/uni/os/targilim/2025B$ tree src_dir/
```
```
src_dir/
├── file1.txt
├── file2.txt
├── subdir1
│   ├── file3.txt
│   └── file4.txt
└── subdir2
    ├── file5.txt
    └── link_to_file1 -> ../file1.txt

2 directories, 6 files
```
After running:
```sh
omer@Omer:~/uni/os/targilim/2025B$ ./backup src_dir/ dest_dir
```
The `dest_dir` directory will contain:
```
dest_dir/
├── file1.txt
├── file2.txt
├── subdir1
│   ├── file3.txt
│   └── file4.txt
└── subdir2
    ├── file5.txt
    └── link_to_file1 -> ../file1.txt

2 directories, 6 files
```

## Why Hard Links Instead of Copying?
- Saves **disk space** (multiple hard links to the same file use one inode).
- **Faster** than copying file content.
- Changes to the original file reflect in all hard links.
- Copies permissions and more **immediately**

## Notes
- The source directory **must exist**, otherwise `perror("src dir")`.
- The backup directory **must not already exist**, otherwise `perror("backup dir")`.
- The copied symbolic links **are not pointing to the original file** but to the copied file (see the example).

## Forum
To make things easier, all the paths inside the src directory will be relative — and relative only.
This isn’t a new requirement, just a small adjustment to help you avoid unnecessary complications :)
If your code worked before - it will still work now.

## Conclusion
This tool is a **fast and efficient** way to back up directories while preserving **hard links and symlinks**, making it useful for versioning, backups, and system management!

## To Make Your Life Easier
I would recommend u to use this functions:
```c
void create_hard_link(const char *src, const char *dst);
void copy_symlink(const char *src, const char *dst);
void copy_directory(const char *src, const char *dst);
```
# 🐧 🐧 🐧 

Make sure to follow the instructions carefully and submit all required files as specified. If you have any questions, feel free to reach out for assistance.

Good luck!
