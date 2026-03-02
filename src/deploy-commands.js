import 'dotenv/config';
import { REST, Routes } from 'discord.js';
import { readdirSync } from 'fs';
import { pathToFileURL, fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const commandsPath = path.join(__dirname, 'commands');
const commands = [];

for (const folder of readdirSync(commandsPath)) {
  const folderPath = path.join(commandsPath, folder);
  for (const file of readdirSync(folderPath).filter(f => f.endsWith('.js'))) {
    const mod = await import(pathToFileURL(path.join(folderPath, file)).href);
    if (mod.data?.toJSON) {
      commands.push(mod.data.toJSON());
      console.log(`Loaded command: ${mod.data.name}`);
    }
  }
}

const rest = new REST().setToken(process.env.DISCORD_TOKEN);
try {
  console.log(`Deploying ${commands.length} application (/) commands...`);
  const data = await rest.put(
    Routes.applicationCommands(process.env.DISCORD_CLIENT_ID),
    { body: commands }
  );
  console.log(`Successfully deployed ${data.length} application (/) commands.`);
} catch (err) {
  console.error(err);
}
