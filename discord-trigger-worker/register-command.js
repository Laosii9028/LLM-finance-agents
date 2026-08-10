const required = [
  "DISCORD_APPLICATION_ID",
  "DISCORD_BOT_TOKEN",
  "DISCORD_GUILD_ID",
];

for (const name of required) {
  if (!process.env[name]) {
    console.error(`缺少環境變數 ${name}`);
    process.exit(1);
  }
}

const url = `https://discord.com/api/v10/applications/${process.env.DISCORD_APPLICATION_ID}` +
  `/guilds/${process.env.DISCORD_GUILD_ID}/commands`;

const response = await fetch(url, {
  method: "POST",
  headers: {
    "authorization": `Bot ${process.env.DISCORD_BOT_TOKEN}`,
    "content-type": "application/json",
  },
  body: JSON.stringify({
    name: "早報",
    description: "立即觸發一次美股與台股早報",
    type: 1,
  }),
});

if (!response.ok) {
  console.error(`註冊失敗 HTTP ${response.status}`, await response.text());
  process.exit(1);
}

console.log("/早報 指令註冊成功：", await response.json());
