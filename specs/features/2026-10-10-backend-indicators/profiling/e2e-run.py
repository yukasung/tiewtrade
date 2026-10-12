import asyncio, base64, os

async def forward(reader, writer, host, port):
    remote_reader, remote_writer = await asyncio.open_connection(host, port)
    async def copy(src, dst):
        try:
            while chunk := await src.read(65536):
                dst.write(chunk)
                await dst.drain()
        finally:
            dst.close()
    await asyncio.gather(copy(reader, remote_writer), copy(remote_reader, writer), return_exceptions=True)

async def main():
    env = dict(os.environ)
    for role in ('migrator','api','engine','engine_scan','market_data','indicator_builder','auth'):
        env['TIEWTRADE_DATABASE_URL_'+role.upper()] = f'postgresql+asyncpg://tiewtrade_{role}:dev_{role}@127.0.0.1:5432/tiewtrade_e2e_f11'
    for role in ('API','MARKET_DATA'):
        env['TIEWTRADE_REDIS_URL_'+role] = 'redis://127.0.0.1:6379/15'
    env['TIEWTRADE_TEST_REDIS_URL'] = 'redis://127.0.0.1:6379/15'
    env['TIEWTRADE_E2E_DATABASE_NAME'] = 'tiewtrade_e2e_f11'
    for purpose, char in [('TOTP_SECRET',b'T'),('VENUE_API_SECRET',b'V'),('INDICATOR_CURSOR',b'I')]:
        env['TIEWTRADE_SEALING_KEY_'+purpose] = '1:'+base64.b64encode(char*32).decode()
    env['CI']='1'
    env['PLAYWRIGHT_JUNIT_OUTPUT_FILE']='/evidence/frontend-e2e-tests.xml'
    pg = await asyncio.start_server(lambda r,w: forward(r,w,'tiewtrade-f11-test-postgres',5432),'127.0.0.1',5432)
    redis = await asyncio.start_server(lambda r,w: forward(r,w,'tiewtrade-f11-test-redis',6379),'127.0.0.1',6379)
    async with pg, redis:
        for cmd, cwd in [(('uv','run','alembic','upgrade','head'),'/app'),(('npm','run','test:e2e','--','--reporter=line,junit'),'/frontend')]:
            process = await asyncio.create_subprocess_exec(*cmd,cwd=cwd,env=env)
            code = await process.wait()
            if code:
                return code
    return 0
raise SystemExit(asyncio.run(main()))