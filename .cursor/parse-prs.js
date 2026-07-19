const fs = require('fs');
const data = JSON.parse(fs.readFileSync('./.cursor/issues.json', 'utf8'));
const prs = data.filter(i => i.pull_request);
console.log('PRs:', prs.length);
prs.forEach(p => {
  const labels = (p.labels || []).map(l => l.name).join(',');
  console.log('#' + p.number + ' [' + p.state + '] ' + p.title + ' | merged_at=' + (p.pull_request.merged_at || '-') + ' | branch=' + p.head.ref + ' -> ' + p.base.ref);
});
