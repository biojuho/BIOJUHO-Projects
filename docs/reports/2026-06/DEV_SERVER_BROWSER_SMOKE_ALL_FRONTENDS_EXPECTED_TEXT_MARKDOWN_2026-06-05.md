# Dev-Server Browser Smoke

- Status: `pass`
- Targets: `4`
- Routes: `10`
- Passed: `10`
- Failed: `0`
- Blocked: `0`

## Results

- `PASS` `dashboard-frontend` `home` `/` expected=`11/11`
- `PASS` `agriguard-frontend` `home` `/` expected=`1/1`
- `PASS` `agriguard-frontend` `registry` `/registry` expected=`1/1`
- `PASS` `agriguard-frontend` `supply-chain` `/supply-chain` expected=`1/1`
- `PASS` `desci-frontend` `home` `/` expected=`1/1`
- `PASS` `desci-frontend` `pricing` `/pricing` expected=`3/3`
- `PASS` `desci-frontend` `explore` `/explore` expected=`2/2`
- `PASS` `desci-frontend` `login` `/login` expected=`1/1`
- `PASS` `desci-frontend` `dashboard-redirect` `/dashboard` expected=`1/1`
- `PASS` `canva-widget-preview` `preview` `` expected=`1/1`

## Expected Text Evidence

- `dashboard-frontend` `home` matched=`11/11`
  - matched: `AI Projects Dashboard`
  - matched: `CREDENTIAL BOUNDARIES`
  - matched: `Next Unblock`
  - matched: `Live plan`
  - matched: `Rank 1 / 2 commands / blocked missing required env`
  - matched: `CANVA_CLIENT_ID, CANVA_CLIENT_SECRET`
  - matched: `Next command`
  - matched: `cd mcp/canva-mcp && npm run doctor:canva`
  - matched: `Queue #2`
  - matched: `GitHub source-refresh token boundary`
  - matched: `Canva OAuth and OpenAPI tool execution`
  - missing: none
- `agriguard-frontend` `home` matched=`1/1`
  - matched: `AgriGuard`
  - missing: none
- `agriguard-frontend` `registry` matched=`1/1`
  - matched: `Register new harvest batches`
  - missing: none
- `agriguard-frontend` `supply-chain` matched=`1/1`
  - matched: `Supply Chain Overview`
  - missing: none
- `desci-frontend` `home` matched=`1/1`
  - matched: `DSCI`
  - missing: none
- `desci-frontend` `pricing` matched=`3/3`
  - matched: `Starter`
  - matched: `Pro`
  - matched: `Enterprise`
  - missing: none
- `desci-frontend` `explore` matched=`2/2`
  - matched: `CRISPR-Cas9`
  - matched: `IPFS`
  - missing: none
- `desci-frontend` `login` matched=`1/1`
  - matched: `DSCI`
  - missing: none
- `desci-frontend` `dashboard-redirect` matched=`1/1`
  - matched: `DSCI`
  - missing: none
- `canva-widget-preview` `preview` matched=`1/1`
  - matched: `Canva Design Widgets`
  - missing: none
