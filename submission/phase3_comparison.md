# Phase 3 — Comparison Writeup

Copy this file to `submission/phase3_comparison.md`, fill in every answer slot, and commit it:

```bash
cp phase-3-mapreduce-spark/comparison_template.md submission/phase3_comparison.md
```

**How to fill it in.** Each answer sits between a pair of `<!--answer:...-->` markers. Replace
the `TODO` line with your answer — **leave the markers themselves untouched**, they are how the
grader finds your answers. Anything you write outside the markers is ignored, so add extra
prose, tables or images freely.

Numbers in section 1 must **match `submission/phase3_report.json`** — copy them across, do not
retype from memory; they are checked against it.

---

## 1. Facts from your runs

Numbers only (e.g. `12`, `20.3`, `0.041`).

| | Value |
|---|---|
| Map tasks in the cloud job (`mapreduce.num_splits`) | <!--answer:num_map_tasks-->12<!--/answer--> |
| Reduce tasks in the cloud job (`mapreduce.num_reducers`) | <!--answer:num_reduce_tasks-->4<!--/answer--> |
| Cloud MapReduce wall time, seconds (`mapreduce.cloud_elapsed_s`) | <!--answer:cloud_elapsed_s-->26.9<!--/answer--> |
| Local single-process wall time, seconds (`mapreduce.local_elapsed_s`) | <!--answer:local_elapsed_s-->0.009<!--/answer--> |
| Spark wall time for the `collect`, seconds (`tfidf.spark_elapsed_s`) | <!--answer:spark_elapsed_s-->9.5<!--/answer--> |
| Number of **stages** in the Spark job (read off notebook 2b / 3a) | <!--answer:num_stages-->4<!--/answer--> |
| Task **retries** you counted in your `--chaos` run (0 if none happened) | <!--answer:chaos_retries-->3<!--/answer--> |

**Explain the timings.** The three wall times above cover the same 60 documents, but not the
same job: the single-process run and the cloud MapReduce are *the same word count*; Spark's
time is for *TF-IDF*, which is more work (two `reduceByKey`s and a `join`). Rank the three and
explain what each is spending its time on. Say which comparison is like-for-like, and what the
Spark number — a heavier job, on one machine — tells you about where the cloud job's time goes.
(~80 words)

<!--answer:timing_explanation-->
Ranking: local 0.009 s < Spark 9.5 s < cloud MapReduce 26.9 s. The like-for-like pair is local vs cloud: the same word count, about 3000x slower in the cloud. The local run is pure computation in one process. The cloud job spends almost all its time on overhead: 16 function invocations (cold starts and OIDC auth), Cloud Storage reads and writes for the inputs, the 48 shuffle files and the outputs, workflow scheduling, and the retry backoff. Spark does more work (two reduceByKeys plus a join) on one machine, yet finishes in a third of the time. Its 9.5 s is mostly JVM, Python-worker and task-scheduling overhead. So the cloud job's time is coordination and I/O, not computation: on a corpus this small, nothing amortises the per-task cost.
<!--/answer-->

**What the counts tell you.** From your stage count: how many shuffles did the Spark job have,
and which operations in `spark_tfidf.py` caused them? From your retry count: roughly what
fraction of the 16 task attempts was retried, and is that what `--chaos 0.3` should produce?
(~50 words)

<!--answer:counts_interpretation-->
4 stages means 3 shuffle boundaries. They are caused by the `reduceByKey` in `term_freq`, the `reduceByKey` in `doc_freq`, and the `join` of tf with df in `build_tfidf_rdd`. The final stage reads the join's shuffle for `collect`. 3 retries over 16 tasks means about 19% of tasks failed at least once. With `--chaos 0.3`, each attempt fails with probability 0.3, so we would expect roughly 5–7 failed attempts. 3 is on the low side but plausible random variation for only 16 tasks.
<!--/answer-->

---

## 2. Spark: transformations, actions, lineage

**Transformations vs actions.** Go through `spark_tfidf.py` and the notebook's Spark cells.
Name each RDD operation and say whether it is a transformation or an action. What happened
when you ran `build_tfidf_rdd` — and what happened when you ran `collect`? (~60 words)

<!--answer:transformations_vs_actions-->
`parallelize` creates the source RDD. `flatMap`, `reduceByKey` (in both `term_freq` and `doc_freq`), `map`, `join` and the final `map` to rows are all transformations: lazy, and only recorded in the lineage. `collect` is the only action. Running `build_tfidf_rdd` returned instantly: it only built the lineage graph that `toDebugString` printed, and no task ran. Running `collect` made Spark split the graph into 4 stages and 12 tasks, execute them, and ship the 5975 rows back to the driver, taking 9.5 s.
<!--/answer-->

**Lineage and recovery.** Using the lineage you printed in 2b and the timeline in 3a: if the
worker holding one output partition of the *first* `reduceByKey` died, what would Spark have
to recompute, and what could it reuse? Name the stage or shuffle boundary where the recovery
starts. (~50 words)

<!--answer:lineage_recovery-->
The first `reduceByKey` is the tf shuffle (`ShuffledRDD[3]`, the boundary between stage 0 and stage 1). Spark would recompute only the lost partition. If stage 0's shuffle files survive, it re-reads them and re-runs the reduce for that one partition. If those map outputs were on the dead worker, it re-runs just those stage-0 map tasks from `ParallelCollectionRDD[0]`. The other partitions and the shuffle files that survived are reused. Only the stage 1 and stage 2 tasks that depend on the lost partition are re-run, not the whole job.
<!--/answer-->

---

## 3. Your cloud MapReduce, mapped onto Hadoop

Name the GCP service or file that played each role (one line each):

- **JobTracker** (schedules tasks, waits for the map phase, retries failures):
  <!--answer:role_jobtracker-->Cloud Workflows: the `mr-wordcount` workflow defined in `workflow.yaml`<!--/answer-->
- **Workers** (run your map and reduce code):
  <!--answer:role_workers-->The `mr-worker` Cloud Run function (`main.py`, entry point `mr_worker`); one invocation per map or reduce task<!--/answer-->
- **HDFS** (holds inputs, shuffle files, outputs):
  <!--answer:role_hdfs-->Cloud Storage: the bucket `<project>-eurecomgpt`, holding `<job>/input/`, `<job>/shuffle/` and `<job>/output/`<!--/answer-->
- **Partitioner** (decides which reducer owns a key):
  <!--answer:role_partitioner-->`partition()` in `mapreduce.py`: `zlib.crc32(word) % num_reducers`, which is stable across processes, unlike `hash()`<!--/answer-->

**The barrier.** There is no explicit "wait for all mappers" step in `workflow.yaml`. Where,
exactly, is the barrier between the map and reduce phases — which construct provides it?
(~30 words)

<!--answer:barrier_location-->
The barrier is the end of the `map_phase` step. It is a `parallel` step with a `for` loop, and a `parallel` step only completes when all of its branches have finished. So the next step, `reduce_phase`, cannot start until the last map task has returned.
<!--/answer-->

**Idempotence.** The workflow retries a task that failed. Why is that safe with the worker as
written, and what would go wrong if `run_map` *appended* its pairs to the shuffle file instead
of overwriting it? (~60 words)

<!--answer:idempotence-->
A map task is deterministic and writes whole files with fixed names: one shuffle file per (split, reducer). Running it twice overwrites the same files with identical content, so a retry leaves exactly the same state as a single run. The chaos failure also happens before any work is done. If `run_map` appended instead, a task that wrote its pairs and then failed, or timed out and was retried, would add its pairs twice. The reducers would then double-count those words, and the result would no longer match the local reference.
<!--/answer-->

**The chaos run.** What did you see in the execution log and in Logs Explorer when you ran
with `--chaos 0.3`? Did the job still succeed, and was the final answer still identical to the
local reference? (~50 words)

<!--answer:chaos_observations-->
In Logs Explorer, the `mr-worker` function logged 3 requests that returned HTTP 503 (the simulated worker crash). In the execution, those tasks were retried by the `try/retry` policy (`http.default_retry_predicate`, exponential backoff) and succeeded on a later attempt. The execution still finished SUCCEEDED in 26.9 s, with 2221 distinct words: identical to the local reference (`matches_local: true`). Failures were absorbed transparently, as a JobTracker would absorb them.
<!--/answer-->
