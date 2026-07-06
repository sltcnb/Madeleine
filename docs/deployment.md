# Deployment

Three modes. All share one image / package.

## 1. Local / CLI

```bash
pip install -e ".[vol]"
mneme --help
```

Offline by default. Best for consultants working single cases.

## 2. Docker (web GUI)

```bash
docker compose up --build
# dashboard: http://localhost:8080   ·   API: http://localhost:8080/api
```

Cases persist under `./data` (mounted to `/data`). Upload raw Vol3 JSON:

```bash
curl -F file=@windows.pslist.json \
  "http://localhost:8080/api/cases/case1/raw?dataset=windows.pslist"
curl http://localhost:8080/api/cases/case1/detections
```

## 3. Kubernetes (multi-user)

```bash
kubectl apply -f k8s/deployment.yaml
```

- 2 replicas behind a LoadBalancer Service
- `PersistentVolumeClaim` for `/data`
- readiness probe on `/healthz`
- non-root, no privilege escalation

**Multi-user model:** each user gets a case subdirectory under `/data/cases`.
Put JWT/OAuth2 + RBAC (admin/analyst/guest) and rate limiting at an ingress
gateway; the API validates case names to block path traversal.

## Config

| Env | Default | Meaning |
|-----|---------|---------|
| `MNEME_DATA` | `/data` | case storage root |

## Resources

Memory analysis is RAM-hungry. Budget ~2× dump size. K8s limits default to
16Gi/4cpu — raise for 32GB+ dumps.
