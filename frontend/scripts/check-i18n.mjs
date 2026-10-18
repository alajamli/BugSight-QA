// Fails if en.js and fr.js do not define exactly the same keys.
import en from '../src/locales/en.js';
import fr from '../src/locales/fr.js';

const missingInFr = Object.keys(en).filter((k) => !(k in fr));
const missingInEn = Object.keys(fr).filter((k) => !(k in en));
if (missingInFr.length || missingInEn.length) {
  if (missingInFr.length) console.error('Missing in fr.js:', missingInFr.join(', '));
  if (missingInEn.length) console.error('Missing in en.js:', missingInEn.join(', '));
  process.exit(1);
}
console.log(`i18n OK: ${Object.keys(en).length} keys in both languages`);
