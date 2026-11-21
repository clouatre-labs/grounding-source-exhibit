# Prompts v2 (grounding-source-exhibit)

## Shared header (prepended to every prompt, all families)

```
The payload below is the ONLY permitted knowledge source. Do not use any
knowledge outside it. If the payload does not determine the answer,
respond with {"answer": null}.
```

## F1: citation edges

Payload: the arm's grounding text (see `recipe/run-bench.sh`).

```
<shared header>

<payload>

Which posts does the post "<title-or-slug>" (slug <slug>) link to,
according to the payload? Respond with JSON {"answer": [<linked post
slugs>]}. If the payload does not determine the answer, respond with
{"answer": null}.
```

## F2: edgeStats inbound/outbound

```
<shared header>

<payload>

How many inbound and outbound links does the post with slug <slug> have
according to the payload? Respond with JSON {"answer": {"inbound": <int>,
"outbound": <int>}}. If the payload does not determine the answer, respond
with {"answer": null}.
```

## F3: node.concepts

```
<shared header>

<payload>

Which concepts are associated with the post with slug <slug> according
to the payload? Respond with JSON {"answer": [<concept slugs>]}. If the
payload does not determine the answer, respond with {"answer": null}.
```

## F4: cluster membership

```
<shared header>

<payload>

Which cluster(s) does the post with slug <slug> belong to, according to
the payload? Respond with JSON {"answer": [<cluster id or name>]}. If the
payload does not determine the answer, respond with {"answer": null}.
```

## Response envelope

A single top-level key `answer` for all families:

- F1 / F3: `{"answer": [<slugs>]}` or `{"answer": null}`
- F2: `{"answer": {"inbound": <int>, "outbound": <int>}}` or
  `{"answer": null}`
- F4: `{"answer": [<cluster id or name>]}` or `{"answer": null}`

The abstention instruction is present in every prompt.
