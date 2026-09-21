# Meta-prompt — drafting a Course Profile with an LLM

Paste the prompt below into a capable LLM (Claude Opus or similar), and attach:

1. The blank `COURSE_PROFILE.md` form.
2. The **Operating Systems** profile, as a worked example of a filled-in one.
3. **One or two of your own past assignments** — the instructions *and*, if you have them,
   two or three real student submissions (one strong, one weak).

That third attachment matters more than the other two. A profile drafted from a course
description is generic; one drafted against real submissions is specific to how your
students actually write code.

---

## The prompt

> You are helping a university course adopt an automated oral-examination system that was
> originally built for an Operating Systems course. In that system, students submit code,
> and an AI examiner then asks each student three questions **about their own submission**
> to verify they genuinely wrote and understand it.
>
> The system is being adapted to my course: **<COURSE NAME>**, which covers
> **<ONE-PARAGRAPH DESCRIPTION>**. Students submit **<WHAT THEY SUBMIT, IN WHAT LANGUAGE>**.
>
> I am attaching: the blank Course Profile form, the filled-in Operating Systems profile as
> an example, and real assignment material from my course.
>
> Your task is to draft my Course Profile. Work through it in this order:
>
> 1. **First, read my attached assignment material** and tell me what a student genuinely
>    has to *decide* when solving it — the points where two competent students would
>    plausibly write different code. Those decision points are where good questions come
>    from. If my assignments turn out to be so prescriptive that there are no real
>    decisions, say so plainly; that is important for me to know before going further.
>
> 2. **Then propose 5–8 question dimensions** for my course. For each: a snake_case name,
>    what it probes, and an example phrasing grounded in my actual assignment. Do not
>    simply translate the Operating Systems dimensions — several of them
>    (`error_handling`, `api_depth`, `cross_file`) may not transfer, and forcing them will
>    produce weak questions. Propose what my field actually needs.
>
>    Apply this test to every dimension you propose: **could someone who merely skimmed
>    this submission answer it, without having reasoned about the work?** If yes, the
>    dimension is weak — it tests reading, not understanding. Explicitly avoid dimensions
>    about syntax, definitions, or terminology: they are memorizable and searchable, and
>    they quietly destroy the system's ability to measure understanding while still
>    producing exams that look reasonable.
>
> 3. **Then fill in the rest of the form**, with particular care on the code-review
>    conventions — especially the list of things that must NOT be penalised in my
>    language/stack. The original reviewer was written for C and will otherwise invent
>    faults (for instance, deducting marks for unchecked memory-allocation return values in
>    a garbage-collected language).
>
> 4. **Finally, flag your own uncertainty.** List the places where you were guessing about
>    my course and where I should check your draft most carefully.
>
> Ask me clarifying questions before drafting if anything material is unclear.

---

## After the draft — calibrate before trusting it

A first draft is a hypothesis. Test it:

1. Generate a question pool for **one past assignment** using the drafted profile.
2. Read ~20 of the generated questions with the course staff.
3. For each, ask: *Is it fair at this point in the semester? Is it about something the
   assignment genuinely required? Could a student answer it without having written the
   code?*
4. Revise the profile — usually the dimension table — and regenerate.

**Two or three rounds is normal.** The most common failure in the first round is
dimensions that are too broad, producing vague questions that any reader of the code could
answer. Tighten them and regenerate.
