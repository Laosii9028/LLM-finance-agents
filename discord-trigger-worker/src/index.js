import { InteractionResponseType, InteractionType, verifyKey } from "discord-interactions";

const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { "content-type": "application/json; charset=utf-8" },
});

function interactionUserId(interaction) {
  return interaction.member?.user?.id || interaction.user?.id || "";
}

function isAllowed(interaction, env) {
  const allowedUsers = (env.ALLOWED_DISCORD_USER_IDS || "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
  if (!allowedUsers.length || !allowedUsers.includes(interactionUserId(interaction))) {
    return false;
  }
  return !env.ALLOWED_DISCORD_GUILD_ID ||
    interaction.guild_id === env.ALLOWED_DISCORD_GUILD_ID;
}

async function dispatchWorkflow(env) {
  const owner = env.GITHUB_OWNER || "Laosii9028";
  const repo = env.GITHUB_REPO || "LLM-finance-agents";
  const workflow = env.GITHUB_WORKFLOW || "daily.yml";
  const ref = env.GITHUB_REF || "main";
  const url = `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${workflow}/dispatches`;

  const response = await fetch(url, {
    method: "POST",
    headers: {
      "accept": "application/vnd.github+json",
      "authorization": `Bearer ${env.GITHUB_TOKEN}`,
      "content-type": "application/json",
      "user-agent": "llm-finance-agents-discord-trigger",
      "x-github-api-version": "2026-03-10",
    },
    body: JSON.stringify({ ref }),
    signal: AbortSignal.timeout(2500),
  });

  if (!response.ok) {
    const detail = (await response.text()).slice(0, 300);
    throw new Error(`GitHub ${response.status}: ${detail}`);
  }
}

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("Discord interactions endpoint", { status: 200 });
    }

    const signature = request.headers.get("x-signature-ed25519") || "";
    const timestamp = request.headers.get("x-signature-timestamp") || "";
    const rawBody = await request.text();
    const valid = await verifyKey(rawBody, signature, timestamp, env.DISCORD_PUBLIC_KEY);
    if (!valid) {
      return new Response("Invalid request signature", { status: 401 });
    }

    const interaction = JSON.parse(rawBody);
    if (interaction.type === InteractionType.PING) {
      return json({ type: InteractionResponseType.PONG });
    }

    if (interaction.type !== InteractionType.APPLICATION_COMMAND ||
        interaction.data?.name !== "早報") {
      return json({
        type: InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
        data: { content: "不支援這個指令。", flags: 64 },
      });
    }

    if (!isAllowed(interaction, env)) {
      return json({
        type: InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
        data: { content: "你沒有觸發早報的權限。", flags: 64 },
      });
    }

    if (!env.GITHUB_TOKEN || !env.DISCORD_PUBLIC_KEY) {
      return json({
        type: InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
        data: { content: "觸發器尚未完成Secret設定。", flags: 64 },
      });
    }

    try {
      await dispatchWorkflow(env);
      return json({
        type: InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
        data: {
          content: "✅ 已觸發早報，GitHub Actions完成後會把報告傳到原本Webhook設定的Discord頻道。",
          flags: 64,
        },
      });
    } catch (error) {
      console.error("workflow dispatch failed", error);
      return json({
        type: InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
        data: {
          content: "❌ 觸發失敗，請查看Cloudflare Worker日誌及GitHub token權限。",
          flags: 64,
        },
      });
    }
  },
};
