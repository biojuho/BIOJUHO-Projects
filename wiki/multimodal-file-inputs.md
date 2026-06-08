---
updated: 2026-06-08T16:00:04+09:00
confidence: medium
source_types:
  - web
  - paper
  - book
sources:
  - id: openai_images_vision
    type: web
    title: OpenAI images and vision
    url: https://developers.openai.com/api/docs/guides/images-vision
    checked: 2026-06-08
  - id: openai_file_inputs
    type: web
    title: OpenAI file inputs
    url: https://developers.openai.com/api/docs/guides/file-inputs
    checked: 2026-06-08
  - id: openai_speech_to_text
    type: web
    title: OpenAI speech to text
    url: https://developers.openai.com/api/docs/guides/speech-to-text
    checked: 2026-06-08
  - id: openai_file_search
    type: web
    title: OpenAI File Search
    url: https://developers.openai.com/api/docs/guides/tools-file-search
    checked: 2026-06-08
  - id: anthropic_vision
    type: web
    title: Anthropic vision
    url: https://platform.claude.com/docs/en/build-with-claude/vision
    checked: 2026-06-08
  - id: anthropic_pdf_support
    type: web
    title: Anthropic PDF support
    url: https://platform.claude.com/docs/en/build-with-claude/pdf-support
    checked: 2026-06-08
  - id: anthropic_citations
    type: web
    title: Anthropic citations
    url: https://platform.claude.com/docs/en/build-with-claude/citations
    checked: 2026-06-08
  - id: google_gemini_files
    type: web
    title: Google Gemini Files API
    url: https://ai.google.dev/gemini-api/docs/files
    checked: 2026-06-08
  - id: google_gemini_vision
    type: web
    title: Google Gemini image understanding
    url: https://ai.google.dev/gemini-api/docs/vision
    checked: 2026-06-08
  - id: docvqa
    type: paper
    title: "DocVQA: A Dataset for VQA on Document Images"
    url: https://arxiv.org/abs/2007.00398
    checked: 2026-06-08
  - id: whisper
    type: paper
    title: "Robust Speech Recognition via Large-Scale Weak Supervision"
    url: https://cdn.openai.com/papers/whisper.pdf
    checked: 2026-06-08
  - id: computer_vision_book
    type: book
    title: "Computer Vision: Algorithms and Applications"
    url: https://szeliski.org/Book/
    checked: 2026-06-08
tags:
  - llm-wiki
  - autoresearch
  - multimodal
  - files
  - pdf
  - audio
  - citations
---

# Multimodal File Inputs

Multimodal file inputs cover images, PDFs, documents, audio, and other uploaded artifacts used by LLM routes. The key product problem is provenance: users need to know which original file, parsed chunk, visual region, transcript, or citation supported the answer.

## Input Contract

```js
const multimodalInput = {
  input_id: "file_20260608_invoice_pdf",
  route_id: "workspace_file_qa",
  media_type: "image|pdf|document|audio|video|mixed",
  original_filename_hash: "sha256:...",
  mime_type: "application/pdf",
  size_bytes: 1842212,
  parser: "openai_file_search|local_pdf_parse|ocr|speech_to_text",
  parser_version: "2026-06-08",
  extracted_artifacts: ["text_chunks", "page_images", "tables", "audio_transcript"],
  citation_mode: "page|span|bounding_box|timestamp|none",
  acl_scope: "workspace_456",
  retention_policy_id: "restricted_30d_redacted_trace",
  eval_fixture_id: "docqa-invoice-v2",
};
```

## Provider Input Shapes

The app should preserve provider-native inputs and an app-owned evidence record:

```js
const providerInputExamples = {
  openai_image: { type: "input_image", image_url: "https://example.com/a.png", detail: "high" },
  openai_file: { type: "input_file", file_id: "file_abc123" },
  anthropic_image: { type: "image", source: { type: "url", url: "https://example.com/a.png" } },
  anthropic_document: { type: "document", source: { type: "file", file_id: "file_pdf123" }, citations: {enabled: true} },
  gemini_file: "createPartFromUri(myfile.uri, myfile.mimeType)",
};
```

OpenAI image routes use `input_image`, `image_url`, and detail modes such as `detail: "low"` and `detail: "high"`; preserve `detail: "original"` as an app policy marker when original-resolution inspection is required before resizing. OpenAI file inputs use `input_file` and reusable `file_id`. Gemini Files API handles media beyond inline request size, with a 20 MB threshold for deciding when to upload. Anthropic multimodal messages distinguish `type: "image"` and `type: "document"`, and document citations can be enabled with `citations: {enabled: true}` / `citations.enabled=true`.

## Modalities

| Input | Main risk | Required evidence |
| --- | --- | --- |
| Image | Visual ambiguity, OCR miss, unsafe or private content. | Image token/cost estimate, visual eval, privacy label. |
| PDF | Text extraction, page order, scanned pages, citation fidelity. | Parser version, page ids, chunk ids, citation spans. |
| Document | Formatting, tables, permissions, stale versions. | Source version, ACL, chunk lineage. |
| Audio | Transcription error, speaker ambiguity, timestamp drift. | Transcript model/version, timestamps, confidence proxy. |
| Mixed file | Model sees some modalities but not others. | Explicit artifact inventory and unsupported-content warning. |

OpenAI vision docs describe image analysis through supported API routes. OpenAI file inputs and File Search docs provide file and retrieval patterns for text/document grounding, including `include: ["file_search_call.results"]` when source chunks must be inspected. Anthropic PDF/citation docs show how answer claims can be tied back to document spans. Gemini Files and Vision docs cover file upload and image understanding paths. DocVQA and Whisper provide benchmark/research context for document-image QA, OCR limits, and speech-to-text errors.

## Ingestion Pipeline Contract

```js
const citationLedger = {
  source_chips: ["invoice.pdf#page=2", "audio.wav#00:01:12"],
  citation_ledger: "cit_20260608_001",
  answer_span: "subtotal is 42.00",
  page_number: 2,
  quote_snippet: "Subtotal 42.00",
  chunking_strategy: "auto",
  timestamp_granularities: ["word", "segment"],
  speech_models: ["gpt-4o-transcribe", "gpt-4o-mini-transcribe", "gpt-4o-transcribe-diarize"],
};
```

For PDFs and documents, capture OCR mode, parser version, page number, quote snippet, chunk id, and source chips. For audio, store speech-to-text model, timestamp_granularities, speaker/diarization caveat, and transcript hash. For file search, preserve chunking_strategy: "auto" and include the file_search_call results when debugging retrieval quality.

## Evaluation Fixtures

| Fixture | Checks |
| --- | --- |
| `pdf_page_citation` | Answer cites the correct page/span for a PDF claim. |
| `scanned_pdf_ocr` | OCR preserves key names, dates, and numbers. |
| `table_extraction` | Table values are not shifted across columns. |
| `image_refusal_boundary` | Model refuses unsupported identity, medical, or safety-sensitive visual claims when policy requires. |
| `audio_timestamp_grounding` | Transcript answer includes correct timestamp range. |
| `acl_rag_boundary` | File from another workspace cannot be retrieved or cited. |
| `file_retention_redaction` | Trace/eval artifacts follow [[data-privacy-retention]]. |

## Citation UX

- PDF answer: show page number and quote snippet hash, not a vague file name.
- Image answer: show crop/bounding-box or region label when claim depends on a visual region.
- Audio answer: show timestamp range and transcript excerpt hash.
- Multi-file answer: show source ranking and which files were ignored.
- Unsupported claim: say that the file did not provide enough evidence.

## A/B 비교: direct multimodal context vs extracted ingestion pipeline

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. Direct multimodal context | 파일을 빠르게 모델에 넣고 UX가 단순하다. | parser version, OCR miss, page/chunk lineage, retention evidence가 약하다. | low-risk one-off analysis. |
| B. Extracted ingestion pipeline | OCR, chunks, tables, transcript, source chips, citation ledger를 앱이 추적한다. | ingestion latency와 저장소 운영이 필요하다. | production knowledge workflow 기본값. |

## A/B 비교: provider-native citations vs app-owned citation ledger

| 선택지 | 장점 | 단점 | 판단 |
| --- | --- | --- | --- |
| A. Provider-native citations | 빠르게 page/span evidence를 얻고 모델별 citation UX를 활용한다. | provider별 형식이 다르고 cross-provider audit/retention이 어렵다. | prototype과 provider-specific route. |
| B. App-owned citation ledger | provider가 바뀌어도 page number, quote snippet, answer_span, ACL, retention을 같은 schema로 감사한다. | mapping adapter가 필요하다. | JooPark customer-facing answer 기본값. |

## Product Hook

JooPark should maintain a file-input evidence drawer:

- original file metadata and ACL;
- parser and parser version;
- extracted artifacts and unsupported portions;
- source chunks, pages, image regions, or timestamps;
- retention and redaction mode;
- linked [[rag-evals]] and failure clusters.

The first-screen UI should remain dense and operational; detailed OCR/transcript/citation artifacts belong in a drill-down panel.

## Open Questions

- Which file types should JooPark support at launch: PDF, image, docx, spreadsheet, audio?
- Should uploaded file parsing be local, provider-side, or hybrid?
- What citation mode is mandatory for customer-facing answers?

## Backlinks

- [[index]]
- [[rag-evals]]
- [[eval-dataset-governance]]
- [[eval-result-lineage]]
- [[data-privacy-retention]]
- [[safety]]
- [[cost-observability]]
- [[source-governance]]

## References

### Web

- OpenAI. "Images and vision." https://developers.openai.com/api/docs/guides/images-vision
- OpenAI. "File inputs." https://developers.openai.com/api/docs/guides/file-inputs
- OpenAI. "File Search." https://developers.openai.com/api/docs/guides/tools-file-search
- OpenAI. "Speech to text." https://developers.openai.com/api/docs/guides/speech-to-text
- Anthropic. "Vision." https://platform.claude.com/docs/en/build-with-claude/vision
- Anthropic. "PDF support." https://platform.claude.com/docs/en/build-with-claude/pdf-support
- Anthropic. "Citations." https://platform.claude.com/docs/en/build-with-claude/citations
- Google. "Gemini Files API." https://ai.google.dev/gemini-api/docs/files
- Google. "Gemini image understanding." https://ai.google.dev/gemini-api/docs/vision

### Paper

- Mathew et al. "DocVQA: A Dataset for VQA on Document Images." arXiv:2007.00398. https://arxiv.org/abs/2007.00398
- Radford et al. "Robust Speech Recognition via Large-Scale Weak Supervision." https://cdn.openai.com/papers/whisper.pdf

### Book

- Szeliski. "Computer Vision: Algorithms and Applications." Springer, 2nd ed. https://szeliski.org/Book/
