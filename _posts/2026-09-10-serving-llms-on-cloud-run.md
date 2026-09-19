---
layout: post
title: "Serving open LLMs on Cloud Run with vLLM"
date: 2026-09-10 09:00:00 +0900
category: AI
tags: [llm, vllm, gcp, infrastructure]
cover: /assets/images/robot_server_room.jpeg
excerpt: "Notes on getting throughput up and cost down when you serve your own models instead of paying per token."
---

Paying per token is fine until it isn't. Once traffic is predictable, hosting an open model
yourself can be dramatically cheaper — if you get the serving layer right.

## Why vLLM

The naive way to serve a model wastes most of the GPU. **vLLM** fixes the two things that
matter most: paged attention for memory efficiency, and continuous batching so requests
don't wait in line for a whole batch to finish.

## Why Cloud Run

I want the model to scale to zero when nobody's using it and spin up on demand. Cloud Run
gives me that with a container and a GPU, no cluster to babysit.

```bash
gcloud run deploy vllm-server \
  --image=$IMAGE --gpu=1 --gpu-type=nvidia-l4 \
  --concurrency=8 --min-instances=0
```

The interesting tuning is in `--concurrency` and vLLM's `--max-num-seqs`: too low and the
GPU idles, too high and latency spikes. I'll write up the throughput curves separately.

More in the [vllm-cloud-run](https://github.com/ValleyJin/vllm-cloud-run) repo.
