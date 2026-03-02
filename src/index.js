import 'dotenv/config';
import { client } from './client.js';
import { loadEvents } from './utils/loader.js';

await loadEvents(client);
await client.login(process.env.DISCORD_TOKEN);
