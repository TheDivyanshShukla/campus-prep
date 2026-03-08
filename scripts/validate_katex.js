/**
 * KaTeX LaTeX Validator
 * 
 * Reads JSON array of math blocks from stdin:
 *   [{ "id": 0, "latex": "\\frac{1}{2}", "displayMode": true }, ...]
 * 
 * Outputs JSON array of results:
 *   [{ "id": 0, "valid": true }, { "id": 1, "valid": false, "error": "..." }, ...]
 */

const katex = require('katex');

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', () => {
    try {
        const blocks = JSON.parse(input);
        const results = blocks.map(block => {
            try {
                katex.renderToString(block.latex, {
                    displayMode: !!block.displayMode,
                    throwOnError: true,
                    strict: false,
                    trust: true,
                    macros: {
                        "\\boxed": "\\fbox{#1}",
                    }
                });
                return { id: block.id, valid: true };
            } catch (e) {
                return { id: block.id, valid: false, error: e.message || String(e) };
            }
        });
        process.stdout.write(JSON.stringify(results));
    } catch (e) {
        process.stderr.write('Invalid JSON input: ' + e.message);
        process.exit(1);
    }
});
