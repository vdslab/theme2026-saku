"""Build the local, timed response form used by the torus readability experiment."""

import argparse
import json
from pathlib import Path, PurePosixPath
import re
from shutil import copyfile

from prepare_torus_readability import CONDITIONS, load


HTML = r"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>有向グラフ読み取り実験</title>
<style>
:root{font-family:system-ui,sans-serif;color:#19364a;background:#eef5f7;line-height:1.55}
*{box-sizing:border-box} [hidden]{display:none!important} main{max-width:76rem;margin:auto;padding:1rem}
section{background:white;border:1px solid #c5d9e1;border-radius:.65rem;padding:1.1rem}
fieldset{border:1px solid #7896a5;display:flex;flex-wrap:wrap;gap:.75rem;margin:.8rem 0}
label{display:inline-block} label:has(input[type=radio]){padding:.45rem .6rem;border-radius:.35rem;background:#eaf4f6}
button,input,select{font:inherit} input,select,button{padding:.45rem;color:inherit}
button{background:#134f69;color:white;border:1px solid #134f69;border-radius:.35rem;cursor:pointer}
button:disabled{opacity:.55;cursor:default}
:focus-visible{outline:3px solid #08796f;outline-offset:3px}
img{width:auto;max-width:100%;max-height:62vh;display:block;margin:.5rem auto}
#status{min-height:1.6em} #status[data-error]{color:#9b3317}
</style></head><body><main>
<h1>有向グラフ読み取り実験</h1>
<p id="status" role="status" aria-live="polite"></p>
<section id="intro">
<p>実施担当者から説明を受けた後に開始してください。矢印の向きに沿って図を読みます。周辺に繰り返しがある図では、枠の反対側に辺が続くことがあります。画像表示から回答確定までの時間を記録します。</p>
<form id="start">
<p><label for="participant">匿名の参加者ID</label> <input id="participant" pattern="[A-Za-z0-9](?:[A-Za-z0-9]|_|-){0,31}"
maxlength="32" required autocomplete="off" aria-describedby="anonymous-help"></p>
<p id="anonymous-help">担当者が割り当てた英数字のIDを入力してください。氏名・メールアドレスは収集しません。</p>
<p><label for="group">担当者が指定したフォーム</label> <select id="group" required>
<option value="">選択</option><option value="0">0</option><option value="1">1</option><option value="2">2</option></select></p>
<button>開始</button>
</form></section>
<section id="trial" hidden>
<h2 id="progress" tabindex="-1"></h2>
<img id="stimulus" alt="AとBが付いた有向グラフ">
<form id="answer-form">
<fieldset id="choices"><legend id="prompt"></legend></fieldset>
<button id="next">回答を確定</button>
</form>
</section>
<section id="done" hidden>
<h2 tabindex="-1" id="done-title">回答が完了しました</h2>
<p>回答CSVを保存し、担当者の指定した方法で提出してください。</p>
<a id="download">回答CSVを保存</a>
</section>
<noscript>回答の記録には JavaScript を有効にしてください。</noscript>
</main>
<script type="application/json" id="forms">__DATA__</script>
<script>
"use strict";
const forms = JSON.parse(document.getElementById("forms").textContent);
const $ = (id) => document.getElementById(id);
const answers = [];
let items, person, group, startedAt, interrupted, attempt = 0;

function choices(task) {
  return task === "direction"
    ? [["A_to_B", "A から B"], ["B_to_A", "B から A"]]
    : ["2", "3", "4", "5"].map(n => [n, n + " 辺"]);
}
function setStatus(message, error = false) {
  $("status").textContent = message;
  $("status").toggleAttribute("data-error", error);
}
async function show() {
  const current = items[answers.length];
  const token = ++attempt;
  startedAt = undefined;
  interrupted = false;
  $("next").disabled = true;
  $("choices").disabled = true;
  $("stimulus").hidden = true;
  $("progress").textContent = (answers.length + 1) + " / " + items.length + " 問";
  $("progress").focus({preventScroll: true});
  $("prompt").textContent = current.prompt;
  $("choices").querySelectorAll("label").forEach(element => element.remove());
  choices(current.task).forEach(([value, text]) => {
    const label = document.createElement("label");
    const option = document.createElement("input");
    option.type = "radio"; option.name = "answer"; option.value = value; option.required = true;
    label.append(option, " " + text);
    $("choices").append(label);
  });
  const image = $("stimulus");
  image.src = current.image;
  try { await image.decode(); } catch {
    setStatus("画像を読み込めません。ページと images フォルダーが同じ場所にあることを担当者に確認してください。", true);
    return;
  }
  if (token !== attempt) return;
  image.hidden = false;
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (token !== attempt) return;
    startedAt = performance.now();
    interrupted = document.hidden;
    $("choices").disabled = false;
    $("next").disabled = false;
    setStatus("");
  }));
}
document.addEventListener("visibilitychange", () => {
  if (document.hidden && startedAt !== undefined) interrupted = true;
});
$("start").addEventListener("submit", (event) => {
  event.preventDefault();
  person = $("participant").value;
  group = $("group").value;
  items = forms[group];
  $("intro").hidden = true;
  $("trial").hidden = false;
  show();
});
function encodeCsv(records) {
  const header = "participant,group,trial,answer,seconds,interrupted";
  return [header, ...records.map(values => values.join(","))].join("\n") + "\n";
}
$("answer-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (startedAt === undefined) return;
  const value = new FormData(event.currentTarget).get("answer");
  if (value === null) return;
  const seconds = Math.max(.001, (performance.now() - startedAt)/1000).toFixed(3);
  answers.push([person, group, items[answers.length].trial, value, seconds, Number(interrupted)]);
  startedAt = undefined;
  if (answers.length < items.length) {
    show();
    return;
  }
  $("trial").hidden = true;
  $("done").hidden = false;
  $("done-title").focus({preventScroll:true});
  const csv = new Blob([encodeCsv(answers)], {type:"text/csv;charset=utf-8"});
  $("download").href = URL.createObjectURL(csv);
  $("download").download = "torus-readability-" + person + ".csv";
});
</script></body></html>
"""


def build(stimuli, output):
    key = {row["trial"]: row["task"] for row in load(stimuli/"answer_key.csv")}
    if len(key) != 24 or not set(key.values()) <= {"direction","distance"}:
        raise ValueError("expected a validated 24-item stimulus set")
    forms = {}
    listed = set()
    rotation = set()
    for form in range(len(CONDITIONS)):
        rows = load(stimuli/f"form_{form}.csv")
        if len(rows)!=24 or {row["trial"] for row in rows}!=set(key):
            raise ValueError("invalid counterbalance form")
        forms[str(form)] = []
        for row in rows:
            image = PurePosixPath(row["image"])
            if not re.fullmatch(r"images/[a-z0-9_-]+[.]png", image.as_posix()) or not (stimuli/image).is_file():
                raise ValueError("unexpected stimulus path")
            if row["condition"] not in CONDITIONS:
                raise ValueError("unknown presentation condition")
            listed.add(image)
            rotation.add((row["trial"],row["condition"]))
            forms[str(form)].append({k:row[k] for k in ("trial","image","prompt")} | {"task":key[row["trial"]]})
    if len(listed)!=72 or len(rotation)!=72:
        raise ValueError("each item needs all three presentation conditions across the forms")
    output.mkdir(parents=True)
    (output/"images").mkdir()
    for image in listed:
        copyfile(stimuli/image,output/image)
    # Inline JSON works under file://. Escaping '<' prevents closing the script element.
    data = json.dumps(forms,ensure_ascii=False).replace("<","\\u003c")
    (output/"index.html").write_text(HTML.replace("__DATA__",data),encoding="utf-8")
    return {"forms":len(forms),"items_per_form":len(key),"images":len(listed)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stimuli",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args()
    summary=build(args.stimuli,args.output)
    (args.output/"build.json").write_text(json.dumps(summary)+"\n",encoding="utf-8")
    print(summary)


if __name__=="__main__":
    main()
