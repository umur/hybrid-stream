# HybridStream

Reference implementation for the paper:

**"A Hybrid Edge-Cloud Stream Processing Framework for Low-Latency Real-Time Analytics"**  
Umur Inan — *Future Generation Computer Systems* (Elsevier, under review)

---

## Overview

HybridStream is a stream processing framework that dynamically places stateful operators across edge and cloud tiers based on real-time resource and network conditions. The core component is the **Adaptive Offloading Decision Engine (AODE)**, which recalibrates operator placement every 5 seconds using a multi-factor scoring model.

Key components:

| Directory | Description |
|---|---|
| `hea/` | HybridStream Edge Agent — lightweight Python 3.12 edge runtime |
| `aode/` | Adaptive Offloading Decision Engine — placement intelligence |
| `flink-connector/` | Java 17 plugin integrating the Flink cloud tier with the AODE |
| `hybridstream-common/` | Shared protobuf types and utilities |
| `proto/` | gRPC service definitions |
| `workloads/` | W1 (Industrial IoT), W2 (Smart City), W3 (Financial) operators |
| `experiments/` | Experiment orchestration and statistical analysis scripts |
| `infra/` | Docker Compose and deployment configurations |
| `schema-registry/` | MessagePack schema versioning |
| `scripts/` | Setup, calibration, and utility scripts |

## Requirements

- Python 3.12+
- Java 17+
- Apache Flink 1.18.x
- Apache Kafka 3.x
- Docker 25+

## Quick Start

```bash
# 1. Start infrastructure (Kafka, MinIO, etcd)
docker compose -f infra/docker-compose.yml up -d

# 2. Start the AODE
cd aode && python -m aode.server

# 3. Start a HEA on an edge node
cd hea && python -m hea.agent --config infra/hea-config.yaml

# 4. Run an experiment
cd experiments && python run_experiment.py --workload W1 --network N2 --runs 10
```

## Reproducing Paper Results

See `experiments/README.md` for full reproduction instructions, including hardware setup, network emulation with `tc netem`, and statistical analysis scripts.

## Citation

```bibtex
@article{inan2026hybridstream,
  author  = {Inan, Umur},
  title   = {A Hybrid Edge-Cloud Stream Processing Framework for Low-Latency Real-Time Analytics},
  journal = {Future Generation Computer Systems},
  year    = {2026},
  note    = {Under review}
}
```
