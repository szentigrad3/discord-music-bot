import { readdirSync } from 'fs';
import { pathToFileURL, fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * Load all event files and register them on the client.
 * @param {import('discord.js').Client} client
 */
export async function loadEvents(client) {
  const eventsPath = path.join(__dirname, '..', 'events');
  const files = readdirSync(eventsPath).filter(f => f.endsWith('.js'));

  for (const file of files) {
    const mod = await import(pathToFileURL(path.join(eventsPath, file)).href);
    const event = mod.default ?? mod;
    if (event.once) {
      client.once(event.name, (...args) => event.execute(...args));
    } else {
      client.on(event.name, (...args) => event.execute(...args));
    }
    console.log(`Loaded event: ${event.name}`);
  }
}

/**
 * Load all command files into client.commands and client.prefixCommands.
 * @param {import('discord.js').Client} client
 */
export async function loadCommands(client) {
  const commandsPath = path.join(__dirname, '..', 'commands');
  const folders = readdirSync(commandsPath);

  for (const folder of folders) {
    const folderPath = path.join(commandsPath, folder);
    const files = readdirSync(folderPath).filter(f => f.endsWith('.js'));

    for (const file of files) {
      const mod = await import(pathToFileURL(path.join(folderPath, file)).href);
      if (mod.data && mod.execute) {
        client.commands.set(mod.data.name, mod);
        client.prefixCommands.set(mod.data.name, mod);
        // Register aliases if any
        if (mod.aliases) {
          for (const alias of mod.aliases) {
            client.prefixCommands.set(alias, mod);
          }
        }
      }
    }
  }
  console.log(`Loaded ${client.commands.size} commands.`);
}
