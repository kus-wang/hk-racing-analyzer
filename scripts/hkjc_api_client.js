#!/usr/bin/env node
"use strict";

const { HKJCClient, horseQuery, horseOddsQuery } = require("hkjc-api");

function parseArgs(argv) {
  const options = {};
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (!arg.startsWith("--")) {
      continue;
    }
    const key = arg.slice(2).replace(/-([a-z])/g, (_, ch) => ch.toUpperCase());
    const next = argv[i + 1];
    if (next && !next.startsWith("--")) {
      options[key] = next;
      i += 1;
    } else {
      options[key] = true;
    }
  }
  return options;
}

function normalizeDate(date) {
  if (!date) {
    return undefined;
  }
  return String(date).replace(/\//g, "-");
}

function normalizeVenue(venue) {
  if (!venue) {
    return undefined;
  }
  return String(venue).toUpperCase();
}

async function main() {
  const [command, ...restArgs] = process.argv.slice(2);
  const options = parseArgs(restArgs);
  const client = new HKJCClient();

  if (!command) {
    throw new Error("Missing command: expected one of meetings, race, odds");
  }

  const date = normalizeDate(options.date);
  const venueCode = normalizeVenue(options.venue);

  if (command === "meetings") {
    const response = await client.request(horseQuery, { date, venueCode });
    console.log(JSON.stringify({
      ok: true,
      result: {
        activeMeetings: response.activeMeetings || [],
        raceMeetings: response.raceMeetings || [],
      },
    }));
    return;
  }

  if (command === "race") {
    const raceNo = Number(options.race || 1);
    const response = await client.request(horseQuery, { date, venueCode });
    const meeting = response.raceMeetings?.[0] || null;
    const race = meeting?.races?.find((item) => Number(item.no) === raceNo) || null;

    console.log(JSON.stringify({
      ok: true,
      result: {
        meeting,
        race,
      },
    }));
    return;
  }

  if (command === "odds") {
    const raceNo = Number(options.race || 1);
    const oddsTypes = String(options.types || "WIN,PLA")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);

    const response = await client.request(horseOddsQuery, {
      date,
      venueCode,
      raceNo,
      oddsTypes,
    });

    console.log(JSON.stringify({
      ok: true,
      result: {
        pmPools: response.raceMeetings?.[0]?.pmPools || [],
      },
    }));
    return;
  }

  throw new Error(`Unknown command: ${command}`);
}

main().catch((error) => {
  console.log(JSON.stringify({
    ok: false,
    error: error?.message || String(error),
  }));
  process.exit(1);
});
