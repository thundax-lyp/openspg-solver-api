

```shell
curl -X 'POST' \
  'http://127.0.0.1:9999/api/openai/v1/chat/completions' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer sk-6K5IuBIAVpHPf4el9dC33540F8F14808A05307Bd24C0183d-fake-key' \
  -d '{
  "model": "openspg/BaiKe",
  "messages": [
    {
      "role": "user",
      "content": "周杰伦曾经为哪些自己出演的电影创作主题曲？"
    }
  ]
}'

```