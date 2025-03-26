# put your registrable modules here


# Streaming Generator

- define stream-llm in your project config, such as:
```yaml
# define stream-llm
generate_llm: &generate_llm
  api_key: { YOUR_API_KEY }
  base_url: { YOUR_BASE_URL }
  model: { YOUR_MODEL }
  type: stream_openai_llm

kag_solver_pipeline:
  generator:
    type: default_generator
    # refer to stream-client 
    llm_client: *generate_llm
```
