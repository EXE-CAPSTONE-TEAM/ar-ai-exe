const fs = require('fs');
const data = JSON.parse(fs.readFileSync('./.cursor/issues.json', 'utf8'));
const issues = data.filter(i => !i.pull_request);
issues.forEach(i => {
  const labels = (i.labels || []).map(l => l.name).join(',');
  console.log('==========');
  console.log('Issue #' + i.number + ' [' + i.state + ']');
  console.log('Title:', i.title);
  console.log('Labels:', labels);
  console.log('Author:', i.user && i.user.login);
  console.log('Created:', i.created_at);
  console.log('--- BODY ---');
  console.log(i.body || '(empty)');
  console.log('--- COMMENTS (' + i.comments + ') ---');
});
