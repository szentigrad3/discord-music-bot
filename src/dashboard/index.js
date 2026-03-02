import 'dotenv/config';
import express from 'express';
import session from 'express-session';
import passport from 'passport';
import { Strategy as DiscordStrategy } from 'passport-discord';
import { fileURLToPath } from 'url';
import path from 'path';
import rateLimit from 'express-rate-limit';
import { doubleCsrf } from 'csrf-csrf';
import { getGuildSettings, updateGuildSettings } from '../db.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const DISCORD_SCOPES = ['identify', 'guilds'];
const MANAGE_GUILD = 0x20;

// ---- Passport setup ----
passport.use(new DiscordStrategy(
  {
    clientID: process.env.DISCORD_CLIENT_ID,
    clientSecret: process.env.DISCORD_CLIENT_SECRET,
    callbackURL: process.env.DISCORD_CALLBACK_URL ?? 'http://localhost:3000/auth/discord/callback',
    scope: DISCORD_SCOPES,
  },
  (accessToken, refreshToken, profile, done) => {
    profile.accessToken = accessToken;
    return done(null, profile);
  },
));

passport.serializeUser((user, done) => done(null, user));
passport.deserializeUser((obj, done) => done(null, obj));

// ---- Express app ----
const app = express();
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.use(express.urlencoded({ extended: true }));
app.use(express.json());
if (!process.env.SESSION_SECRET) {
  console.error('FATAL: SESSION_SECRET environment variable is not set. Refusing to start.');
  process.exit(1);
}

app.use(session({
  secret: process.env.SESSION_SECRET,
  resave: false,
  saveUninitialized: false,
  cookie: { secure: process.env.NODE_ENV === 'production', maxAge: 7 * 24 * 60 * 60 * 1000 },
}));
app.use(passport.initialize());
app.use(passport.session());

// ---- Rate limiting ----
const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 30,
  standardHeaders: true,
  legacyHeaders: false,
  message: 'Too many requests, please try again later.',
});

// ---- CSRF protection ----
const { generateToken, doubleCsrfProtection } = doubleCsrf({
  getSecret: () => process.env.SESSION_SECRET,
  cookieName: '__Host-psifi.x-csrf-token',
  cookieOptions: {
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'strict',
  },
});

// ---- Auth middleware ----
function ensureAuth(req, res, next) {
  if (req.isAuthenticated()) return next();
  res.redirect('/');
}

// ---- Routes ----
app.get('/', authLimiter, (req, res) => {
  if (req.isAuthenticated()) return res.redirect('/dashboard');
  res.render('index', { user: null });
});

app.get('/auth/discord', authLimiter, passport.authenticate('discord'));

app.get('/auth/discord/callback',
  authLimiter,
  passport.authenticate('discord', { failureRedirect: '/' }),
  (req, res) => res.redirect('/dashboard'),
);

app.get('/auth/logout', authLimiter, (req, res, next) => {
  req.logout(err => {
    if (err) return next(err);
    res.redirect('/');
  });
});

app.get('/dashboard', authLimiter, ensureAuth, async (req, res) => {
  const user = req.user;
  // Filter guilds where user has Manage Guild
  const manageableGuilds = (user.guilds ?? []).filter(g => (parseInt(g.permissions) & MANAGE_GUILD) === MANAGE_GUILD);

  // Attempt to check which guilds the bot is in (requires bot client import)
  // When running standalone, we skip the bot presence check
  let botGuildIds = new Set();
  try {
    const { client } = await import('../client.js');
    if (client.isReady()) {
      botGuildIds = new Set(client.guilds.cache.keys());
    }
  } catch { /* standalone mode */ }

  const guildsWithPresence = manageableGuilds.map(g => ({
    ...g,
    botPresent: botGuildIds.has(g.id),
  }));

  res.render('dashboard', { user, guilds: guildsWithPresence });
});

app.get('/dashboard/:guildId/settings', authLimiter, ensureAuth, async (req, res) => {
  const { guildId } = req.params;
  const user = req.user;

  const hasAccess = (user.guilds ?? []).some(
    g => g.id === guildId && (parseInt(g.permissions) & MANAGE_GUILD) === MANAGE_GUILD,
  );
  if (!hasAccess) return res.status(403).send('Forbidden');

  const settings = await getGuildSettings(guildId).catch(() => ({}));
  const csrfToken = generateToken(req, res);
  res.render('settings', { user, guildId, settings, saved: false, csrfToken });
});

app.post('/dashboard/:guildId/settings', authLimiter, ensureAuth, doubleCsrfProtection, async (req, res) => {
  const { guildId } = req.params;
  const user = req.user;

  const hasAccess = (user.guilds ?? []).some(
    g => g.id === guildId && (parseInt(g.permissions) & MANAGE_GUILD) === MANAGE_GUILD,
  );
  if (!hasAccess) return res.status(403).send('Forbidden');

  const { prefix, language, defaultVolume, djRoleId, announceNowPlaying } = req.body;

  await updateGuildSettings(guildId, {
    prefix: prefix?.slice(0, 5) || '!',
    language: ['en', 'es'].includes(language) ? language : 'en',
    defaultVolume: Math.max(1, Math.min(100, parseInt(defaultVolume) || 80)),
    djRoleId: djRoleId || null,
    announceNowPlaying: announceNowPlaying === 'on',
  });

  const settings = await getGuildSettings(guildId).catch(() => ({}));
  const csrfToken = generateToken(req, res);
  res.render('settings', { user, guildId, settings, saved: true, csrfToken });
});

// ---- Start ----
const PORT = process.env.DASHBOARD_PORT ?? 3000;
app.listen(PORT, () => {
  console.log(`🌐 Dashboard running at http://localhost:${PORT}`);
});

export default app;
