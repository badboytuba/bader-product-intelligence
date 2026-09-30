// Safety boundary shared by destructive throwaway-clone regression scripts.
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const BASE=process.env.BPI_TEST_BASE,DB=process.env.BPI_TEST_DB;
assert(/^http:\/\/127\.0\.0\.1:[0-9]+$/.test(BASE || ''), 'Use a loopback tunnel to an isolated clone.');
assert(/^bpi_variant_test_[0-9_]+$/.test(DB || ''), 'Never run on a live database.');
assert(process.env.BPI_TEST_CREDENTIALS, 'Provide protected clone-only credentials.');
const dir=path.resolve(process.env.BPI_TEST_ARTIFACTS || '/tmp/bpi-variant-smoke');fs.mkdirSync(dir,{recursive:true,mode:0o700});
const credentials=JSON.parse(fs.readFileSync(process.env.BPI_TEST_CREDENTIALS));
module.exports={BASE,DB,dir,credentials,chromium:require(process.env.BPI_PLAYWRIGHT_MODULE || 'playwright').chromium};
