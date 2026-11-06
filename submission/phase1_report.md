# Phase 1 — Comparison Report

## 1. Setup facts

**Your image size**, in MB, from `gcloud artifacts docker images list` (number only, e.g. `142`):

<!--answer:image_size_mb-->
48
<!--/answer-->

**The custom VPC and subnet you created** (names only):

<!--answer:vpc_name-->
echo-net
<!--/answer-->

<!--answer:subnet_name-->
echo-subnet
<!--/answer-->

---

## 2. Measurements

| Platform | Cold (ms) | Warm median (ms) |
|---|---|---|
| IaaS VM | <!--answer:vm_cold_ms-->305.2<!--/answer--> | <!--answer:vm_warm_median_ms-->212.4<!--/answer--> |
| Cloud Run | <!--answer:cloudrun_cold_ms-->2019.7<!--/answer--> | <!--answer:cloudrun_warm_median_ms-->632.6<!--/answer--> |
| Cloud Function | <!--answer:function_cold_ms-->1876.2<!--/answer--> | <!--answer:function_warm_median_ms-->636.2<!--/answer--> |

<!--answer:latency_plot-->
Phase 1 — warm-median latency (ms)

VM        | ############# 212.4
Cloud Run | ######################################## 632.6
Function  | ######################################## 636.2

Cold starts:
VM        | ##### 305.2
Cloud Run | ######################################## 2019.7
Function  | ##################################### 1876.2

Full distributions are in phase1_report.json. Cloud Run and Function warm samples
are bimodal (clusters around ~120 ms and ~640 ms), reflecting whether the request
hit an already-warm instance or triggered a short internal routing hop.
<!--/answer-->

---

## 3. Per-platform analysis

<!--answer:scaling_behaviour-->
The VM is a fixed e2-micro: nothing is created when load rises. Under one request it sits idle; under ten or a hundred it saturates its single container on one vCPU and starts queuing or dropping. Its hard limit comes from the machine type I picked (--machine-type=e2-micro). Cloud Run and the Function both auto-scale per concurrency: Google spins up additional container instances to absorb simultaneous requests, capped at --max-instances=3 which I set myself. Their hard limit is my flag, not the box size, so raising the cap raises capacity with no reprovisioning on my side.
<!--/answer-->

<!--answer:deployment_effort-->
The VM took the most work: create a custom VPC echo-net and subnet echo-subnet, open two firewall rules (8080 for HTTP, 22 over IAP for SSH), choose a Debian 12 image and machine type, grant the Compute Engine service account roles/artifactregistry.reader so it can pull, SSH in, install Docker, run gcloud auth configure-docker, then docker pull and docker run -d --restart=always -p 8080:8080 the image. Cloud Run reused the exact same image with one command — I only passed the image URI, port, --min-instances=0, --max-instances=3, and --allow-unauthenticated; networking, TLS, scaling and routing are managed. The Function took even less: no Dockerfile at all, just source, a Python 3.11 runtime, an entry point echo, and --trigger-http.
<!--/answer-->

---

## 4. Why do two of your three numbers look alike?

<!--answer:run_services_list-->
   SERVICE: echo
   REGION: us-central1
   URL: https://echo-809596718607.us-central1.run.app
   LAST DEPLOYED BY: service-809596718607@gcf-admin-robot.iam.gserviceaccount.com
   LAST DEPLOYED AT: 2026-11-06T19:00:13.187900Z

   SERVICE: echo-bot
   REGION: us-central1
   URL: https://echo-bot-809596718607.us-central1.run.app
   LAST DEPLOYED BY: Mohamed-Amine.Trabelsi@eurecom.fr
   LAST DEPLOYED AT: 2026-11-06T18:57:49.100356Z
<!--/answer-->

<!--answer:convergence_explanation-->
gcloud run services list returns two services in us-central1: echo-bot (my Cloud Run deployment) and echo (what I deployed as a gen-2 Cloud Function). gen-2 Functions do not run on the legacy Functions infrastructure — Google packages the source with the Functions Framework, builds a container, and deploys it as a Cloud Run service. That is why echo even appears in this list, is "last deployed by" the gcf-admin-robot service agent, and serves traffic on a .run.app URL. Because both endpoints are ultimately the same Cloud Run container runtime, their cold starts (~2.0 s vs ~1.9 s) and warm medians (632 ms vs 636 ms) are nearly identical: the ~2 s cold is dominated by the same container boot plus Python/gunicorn startup. What genuinely differs is the developer contract. Cloud Run makes me own the Dockerfile, the HTTP server (gunicorn), the port, and the image lifecycle. The Function hides all of that behind functions_framework.http and a --source directory — I just write a function and Google builds and runs the container for me.
<!--/answer-->