# Kubernetes Deployment for Every Now & Then

This directory contains Kubernetes manifests for deploying the Every Now & Then script runner to a Kubernetes cluster.

## Prerequisites

- Kubernetes cluster (DigitalOcean Kubernetes used in the example)
- `kubectl` configured to access your cluster
- Docker Hub account for container registry
- Google Cloud Service Account JSON file (if using Google APIs)

## ConfigMaps

The deployment requires two ConfigMaps:

### 1. Environment Variables ConfigMap (`every-nownthen-env-config`)

Contains all environment variables needed by your scripts.

**Create from .env file:**

```bash
kubectl create configmap every-nownthen-env-config \
  --from-env-file=.env \
  --namespace=vetify
```

**Or create manually:**

```bash
kubectl apply -f configmap-env.example.yaml
```

### 2. Service Account ConfigMap (`every-nownthen-service-account-key-path-config`)

Contains the Google Cloud Service Account JSON file.

**Create from JSON file:**

```bash
kubectl create configmap every-nownthen-service-account-key-path-config \
  --from-file=service_account.json=/path/to/your/service-account-key.json \
  --namespace=vetify
```

## GitHub Secrets and Variables

Configure these in your GitHub repository settings:

### Secrets (Settings → Secrets and variables → Actions → Secrets)

- `DOCKERHUB_USERNAME` - Your Docker Hub username
- `DOCKERHUB_TOKEN` - Docker Hub access token
- `DIGITALOCEAN_ACCESS_TOKEN` - DigitalOcean API token

### Variables (Settings → Secrets and variables → Actions → Variables)

- `DOCKERHUB_USERNAME` - Your Docker Hub username (for image naming)
- `DIGITALOCEAN_K8S_CLUSTER_NAME` - Your Kubernetes cluster name
- `K8S_NAMESPACE` - Kubernetes namespace (default: `default`)

## Deployment Steps

### 1. Create ConfigMaps

Before deploying, create the required ConfigMaps in your cluster:

```bash
# Create environment variables ConfigMap
kubectl create configmap every-nownthen-env-config \
  --from-env-file=../../.env \
  --namespace=default

# Create service account ConfigMap
kubectl create configmap every-nownthen-service-account-key-path-config \
  --from-file=service_account.json=/path/to/service-account.json \
  --namespace=default
```

### 2. Verify ConfigMaps

```bash
# List ConfigMaps
kubectl get configmaps --namespace=default

# View ConfigMap content (be careful with sensitive data)
kubectl describe configmap every-nownthen-env-config --namespace=default
kubectl describe configmap every-nownthen-service-account-key-path-config --namespace=default
```

### 3. Deploy via GitHub Actions

The deployment is automated via GitHub Actions when you push a tag:

```bash
# Create and push a tag
git tag v1.0.0
git push origin v1.0.0
```

This will:

1. Build the Docker image
2. Push to Docker Hub
3. Deploy to Kubernetes cluster
4. Verify the deployment

### 4. Manual Deployment

You can also deploy manually:

```bash
# Build and push the image
docker build -t yourusername/every-nownthen:latest .
docker push yourusername/every-nownthen:latest

# Update the deployment.yaml with your image
sed -i "s|<IMAGE>|yourusername/every-nownthen:latest|" deployment.yaml

# Apply to cluster
kubectl apply -f deployment.yaml

# Verify deployment
kubectl get deployments --namespace=default
kubectl get pods --namespace=default
```

## Monitoring

### View Logs

```bash
# Get pod name
kubectl get pods --namespace=default -l app=every-nownthen

# View logs
kubectl logs -f <pod-name> --namespace=default

# View cron logs specifically
kubectl exec -it <pod-name> --namespace=default -- tail -f /var/log/cron.log
```

### Check Pod Status

```bash
# Get pod details
kubectl describe pod <pod-name> --namespace=default

# Check deployment status
kubectl rollout status deployment/every-nownthen --namespace=default
```

## Updating ConfigMaps

When you need to update environment variables or the service account:

```bash
# Update environment variables
kubectl create configmap every-nownthen-env-config \
  --from-env-file=../../.env \
  --namespace=default \
  --dry-run=client -o yaml | kubectl apply -f -

# Restart the deployment to pick up changes
kubectl rollout restart deployment/every-nownthen --namespace=default
```

## Storage

The deployment includes a PersistentVolumeClaim for data storage:

- **Name:** `every-nownthen-data-pvc`
- **Size:** 5Gi
- **Access Mode:** ReadWriteOnce
- **Storage Class:** `do-block-storage` (DigitalOcean Block Storage)

Data is persisted at `/data` inside the container.

## Troubleshooting

### ConfigMap not found

```bash
# List all ConfigMaps
kubectl get configmaps --all-namespaces

# Ensure ConfigMaps are in the correct namespace
kubectl get configmaps --namespace=default
```

### Service Account JSON not loading

```bash
# Check if the file is mounted correctly
kubectl exec -it <pod-name> --namespace=default -- ls -la /etc/service_account.json

# View the ConfigMap data
kubectl get configmap every-nownthen-service-account-key-path-config -o yaml
```

### Environment variables not set

```bash
# Check environment variables inside pod
kubectl exec -it <pod-name> --namespace=default -- env | grep GREETING

# Verify ConfigMap
kubectl describe configmap every-nownthen-env-config --namespace=default
```

### Cron jobs not running

```bash
# Check cron logs
kubectl exec -it <pod-name> --namespace=default -- cat /var/log/cron.log

# Verify crontab is installed
kubectl exec -it <pod-name> --namespace=default -- crontab -l
```

### Pod crashes or restarts

```bash
# Check pod events
kubectl describe pod <pod-name> --namespace=default

# View previous logs (if pod restarted)
kubectl logs <pod-name> --namespace=default --previous
```

## Security Considerations

1. **Secrets Management:**
   - Never commit ConfigMaps with real credentials to Git
   - Consider using Kubernetes Secrets instead of ConfigMaps for sensitive data
   - Use sealed-secrets or external secret management (Vault, AWS Secrets Manager)

2. **Service Account:**
   - Use minimal permissions for the Google Service Account
   - Rotate service account keys regularly
   - Consider using Workload Identity (GKE) instead of JSON keys

3. **Container Security:**
   - The container currently runs as root - consider adding a non-root user
   - Implement pod security policies
   - Scan images for vulnerabilities

4. **Network Security:**
   - Add NetworkPolicies to restrict traffic
   - Use ingress/egress rules as needed

## Resource Limits

Current resource configuration:

```yaml
requests:
  memory: "256Mi"
  cpu: "100m"
limits:
  memory: "512Mi"
  cpu: "500m"
```

Adjust these based on your script requirements.

## Cleanup

To remove the deployment:

```bash
# Delete deployment and PVC
kubectl delete -f deployment.yaml

# Delete ConfigMaps
kubectl delete configmap every-nownthen-env-config --namespace=default
kubectl delete configmap every-nownthen-service-account-key-path-config --namespace=default
```

## Next Steps

1. Adjust resource limits based on monitoring
2. Implement horizontal pod autoscaling if needed
3. Add monitoring and alerting (Prometheus, Grafana)
4. Implement backup strategy for persistent data
5. Set up log aggregation (Loki, ELK stack)
