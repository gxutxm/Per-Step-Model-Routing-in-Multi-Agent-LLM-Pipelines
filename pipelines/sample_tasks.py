import json, random, collections

SEED = 42
N = 150
BIRD_FILE = "data/bird/minidev/MINIDEV/mini_dev_sqlite.json"
HOTPOT_FILE = "data/hotpot/hotpot_dev_distractor_v1.json"


def proportional_sample(items, key, n, rng):
    groups = collections.defaultdict(list)
    for it in items:
        groups[key(it)].append(it)
    total = len(items)
    raw = {k: n * len(v) / total for k, v in groups.items()}
    alloc = {k: int(r) for k, r in raw.items()}
    leftover = n - sum(alloc.values())
    for k in sorted(raw, key=lambda k: raw[k] - alloc[k], reverse=True)[:leftover]:
        alloc[k] += 1
    out = []
    for k in sorted(groups):
        out += rng.sample(groups[k], alloc[k])
    return out, alloc


def main():
    rng = random.Random(SEED)

    bird = json.load(open(BIRD_FILE))
    bird_s, a = proportional_sample(bird, lambda q: q["difficulty"], N, rng)
    print("BIRD sample:", a, "total", len(bird_s))
    json.dump(bird_s, open("data/bird_sample_150.json", "w"), indent=1)

    hotpot = json.load(open(HOTPOT_FILE))
    hp_s, b = proportional_sample(hotpot, lambda q: q["type"], N, rng)
    print("HotpotQA sample:", b, "total", len(hp_s))
    json.dump(hp_s, open("data/hotpot_sample_150.json", "w"), indent=1)


if __name__ == "__main__":
    main()
