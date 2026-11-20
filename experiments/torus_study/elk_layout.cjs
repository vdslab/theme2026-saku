const fs = require('node:fs');
const ELK = require(process.argv[2]);

async function main() {
  const graph = JSON.parse(fs.readFileSync(0, 'utf8'));
  const layout = await new ELK().layout(graph);
  process.stdout.write(JSON.stringify(layout));
}

main().catch(error => {
  process.stderr.write(String(error) + '\n');
  process.exitCode = 1;
});
