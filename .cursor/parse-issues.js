const fs = require('fs');
const data = JSON.parse(fs.readFileSync('./.cursor/issues.json', 'utf8'));
console.log('Total entries:', data.length);
const issues = data.filter(i => !i.pull_request);
const prs = data.filter(i => i.pull_request);
console.log('Issues:', issues.length, 'PRs:', prs.length);
console.log('---ISSUES---');
issues.forEach(i => {
  const labels = (i.labels || []).map(l => l.name).join(',');
  console.log('#' + i.number + ' [' + i.state + '] ' + i.title + ' | labels=' + labels);
});
