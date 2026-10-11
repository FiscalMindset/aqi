# Cost

Estimated monthly cost at demo scale, sized deliberately small, plus teardown.

## Assumptions

- 1 Delhi-NCR deployment, ~2,300 H3 cells, hourly pipeline (730 runs/month)
- ~50k API requests/month, ~2k `/v1/explain` calls/month
- OpenSearch: single-node `t3.small.search` equivalent (or a managed domain with one data node)
- Lambda: 512 MB API / 2048 MB pipeline, arm64, ~5 min per pipeline run

## Monthly estimate (ap-south-1, USD)

| Service | Configuration | ~Cost |
|---|---|---|
| Lambda (API) | ~50k requests × 300 ms × 512 MB, arm64 | < $1 |
| Lambda (pipeline) | 730 × 5 min × 2048 MB, arm64 | ~$2 |
| API Gateway | 50k REST API calls | ~$0.20 |
| DynamoDB | on-demand, < 1 GB, PITR on 3 tables | ~$1.50 |
| OpenSearch | 1 × t3.small.search + 20 GB EBS | ~$40 |
| S3 + CloudFront | < 5 GB, < 100k requests | ~$2 |
| SNS | 2k email notifications | < $0.50 |
| EventBridge / Step Functions | 730 hourly transitions | ~$0.30 |
| CloudWatch + X-Ray | logs, 8 alarms, tracing | ~$5 |
| Amazon Location Service | 100k map tile requests + 1k routes | ~$3 |
| Bedrock (explains) | 2k calls × ~4k tokens | ~$10 |
| **Total** | | **~$65/month** |

The dominant cost is the OpenSearch node. For a demo, a single node is enough; for prod, consider a domain with a standby node (~2×).

## Cost guardrails in the code

- Smallest resource sizes (`MemorySize: 512` for the API, `1024` with 30 s timeout).
- Log retention set in the template (30 days default).
- DynamoDB TTL expires estimates after 90 days.
- S3 lifecycle rule expires `raw/` prefixes after 90 days.
- The pipeline runs hourly, not per-minute.

## Budget alarm

```yaml
# add via the AWS Budgets console or the console CLI:
aws budgets create-budget --account-id $ACCOUNT_ID --budget file://budget.json
# e.g. 100 USD monthly with alerts at 80% and 100%
```

## Teardown

```bash
scripts/teardown.sh
```

removes the CloudFormation stack, both website buckets and their CloudFront distribution, the SNS topic, and the DLQ — everything the template created. Nothing else is touched.
