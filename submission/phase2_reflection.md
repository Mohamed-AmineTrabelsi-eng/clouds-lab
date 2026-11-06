# Phase 2 — Reflection: where does parallelism stop helping?

## 1. Your measurements

| | Value |
|---|---|
| Naive attention, ms (`attention.naive_ms`) | <!--answer:attn_naive_ms-->272.122<!--/answer--> |
| Vectorized attention, ms (`attention.vectorized_ms`) | <!--answer:attn_vectorized_ms-->1.222<!--/answer--> |
| CPU training, ms for 100 steps (`devices.cpu_ms`) | <!--answer:cpu_ms-->474622.6<!--/answer--> |
| GPU training, ms for 100 steps (`devices.gpu_ms`) | <!--answer:gpu_ms-->13433.0<!--/answer--> |
| Final training loss (`training.final_loss`) | <!--answer:final_loss-->1.4818<!--/answer--> |

<!--answer:thread_sweep-->
1 thread: 3005.765 ms, 2 threads: 2765.003 ms, 4 threads: 2477.951 ms, 8 threads: 2409.438 ms. The fastest count was 8 threads, but the gain from 4 to 8 was tiny (~68 ms, under 3%), so the curve is already flat by 4 threads.
<!--/answer-->

---

## 2. Intra-node parallelism, three ways

<!--answer:vectorization_why-->
The naive attention time (272 ms) goes almost entirely into the Python interpreter: every scalar multiply-add is a separate bytecode dispatch with per-op object boxing and no CPU-level SIMD. The vectorized version (1.22 ms, 222.7x faster) hands the whole QK^T and softmax(QK^T)V as contiguous NumPy arrays to OpenBLAS; that BLAS kernel is written in C and uses X86_V3/V4 SIMD registers (AVX2/AVX-512) so one instruction multiplies 8-16 floats at once. The arithmetic is identical; the delivery to the CPU ALUs is not.
<!--/answer-->

<!--answer:threading_plateau-->
The sweep drops hard from 1 to 4 threads (3006 -> 2478 ms, about 20 percent faster) and almost flattens from 4 to 8 (2478 -> 2409, under 3 percent). Colab's free runtime gives only 2 vCPUs, so past 2 real cores PyTorch threads start fighting for the same compute and memory bandwidth instead of adding work. Intra-op threads also have to synchronize on each matmul output; that barrier cost is paid by every extra thread and eventually wipes out the parallelism gain.
<!--/answer-->

<!--answer:gpu_why-->
A transformer training step is dominated by large dense matmuls (Q*K^T, softmax*V, feed-forward, embeddings). Those map perfectly onto a T4's thousands of CUDA cores running the same instruction on different data (SIMT), hitting 35.3x here (474,623 ms vs 13,433 ms). A workload that would NOT see this speed-up: a tight serial loop where each step depends on the previous one, for example autoregressive single-token inference at batch size 1, where there is no parallel work to feed the GPU and the kernel-launch overhead dominates.
<!--/answer-->

---

## 3. The question

<!--answer:parallelism_limit-->
Each experiment hit a different wall. Vectorization is bound by what the hardware supports: we got 222.7x because the CPU has AVX SIMD lanes; without them the ceiling would be 1x. Threading is bound by hardware we do not have plus coordination cost: with only 2 vCPUs on the Colab host, the 4- and 8-thread settings share physical cores (3006 to 2410 ms, barely 1.25x of the ideal 8x) and barrier synchronization on every matmul erodes the rest. GPU is bound by data movement and work granularity: it crushed the CPU (474,623 vs 13,433 ms, 35.3x) because every step has enough matmul work to hide PCIe host-to-device transfers; shrink the batch or the layer width and launch and copy costs would dominate instead. Amdahl's law threads through all three: the serial parts (tokenization, backward dependencies, gradient sync) place an absolute cap no amount of parallelism can beat.
<!--/answer-->

<!--answer:next_experiment-->
Repeat the GPU training with a tiny batch (for example 1 instead of 16) and measure CUDA kernel-launch and host-to-device time with torch.profiler. If per-step time barely shrinks relative to the CPU baseline, that confirms the GPU speed-up here comes from amortizing launch and transfer costs over a large batch, which would change my explanation in section 2.
<!--/answer-->
