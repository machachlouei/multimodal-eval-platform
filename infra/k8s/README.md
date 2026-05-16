# Kubernetes manifests

Skeleton only. Each control-plane service should be deployed as its own
`Deployment` + `Service` (§5.2, §12.2). The data plane and judge plane belong
on separate node pools with `NetworkPolicy` restricting egress so that only
the judge plane can reach the LLM gateway (§9.6).

Recommended layout in production:

```
k8s/
  base/
    gateway-deploy.yaml
    authz-deploy.yaml
    run-deploy.yaml
    ...
    pvc-postgres.yaml
    networkpolicy-judge-egress.yaml
  overlays/
    dev/
    staging/
    prod/
```

Use Kustomize or Helm to layer environment overrides. Not committed in this
phase — the docker-compose stack is enough for Phase 1 + Phase 2 development.
