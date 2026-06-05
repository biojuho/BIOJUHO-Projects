# Canva Widget Click Smoke

- Status: `pass`
- URL: `http://127.0.0.1:5176/src/dev/preview.html`
- Actions: `9`
- Passed: `9`
- Failed: `0`
- Messages: `5`

## Actions

- `PASS` `load-preview` - loaded status=200
- `PASS` `toggle-theme` - dark_before=false dark_after=true
- `PASS` `scroll-candidates-right` - clicked Scroll design candidates right
- `PASS` `scroll-candidates-left` - clicked Scroll design candidates left
- `PASS` `select-candidate-click` - canva-create-from-candidate.candidateId=candidate_1
- `PASS` `select-candidate-keyboard` - canva-create-from-candidate.candidateId=candidate_2 via Enter
- `PASS` `open-design-click` - canva-design-clicked.designId=design_1
- `PASS` `open-design-keyboard` - canva-design-clicked.designId=design_2 via Space
- `PASS` `load-more-click` - canva-load-more.continuation=next_page_token_xyz

## Messages

- `0` `canva-create-from-candidate` `candidate_1`
- `1` `canva-create-from-candidate` `candidate_2`
- `2` `canva-design-clicked` `design_1`
- `3` `canva-design-clicked` `design_2`
- `4` `canva-load-more` `next_page_token_xyz`
