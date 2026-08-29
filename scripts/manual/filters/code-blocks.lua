local generic_labels = {
  ca = "Codi",
  es = "Código",
  en = "Code",
}

local generic_languages = {
  text = true,
  plaintext = true,
  plain = true,
  txt = true,
}

local language_labels = {
  bash = "Bash",
  c = "C",
  console = "Console",
  cpp = "C++",
  csharp = "C#",
  css = "CSS",
  go = "Go",
  haskell = "Haskell",
  html = "HTML",
  java = "Java",
  javascript = "JavaScript",
  js = "JavaScript",
  json = "JSON",
  julia = "Julia",
  latex = "LaTeX",
  markdown = "Markdown",
  matlab = "MATLAB",
  php = "PHP",
  powershell = "PowerShell",
  python = "Python",
  r = "R",
  ruby = "Ruby",
  rust = "Rust",
  shell = "Shell",
  sh = "Shell",
  sql = "SQL",
  typescript = "TypeScript",
  ts = "TypeScript",
  xml = "XML",
  yaml = "YAML",
  yml = "YAML",
}

local listings_languages = {
  bash = "bash",
  python = "Python",
  r = "R",
  shell = "bash",
  sh = "bash",
  sql = "SQL",
}

local function normalized_language(meta)
  local raw = pandoc.utils.stringify(meta.lang or "en"):lower()
  return raw:match("^[^-_]+") or "en"
end

local function title_case(value)
  local words = {}
  for word in value:gmatch("[^-_]+") do
    table.insert(words, word:sub(1, 1):upper() .. word:sub(2))
  end
  return table.concat(words, " ")
end

local function latex_escape(value)
  local replacements = {
    ["\\"] = "\\textbackslash{}",
    ["{"] = "\\{",
    ["}"] = "\\}",
    ["$"] = "\\$",
    ["&"] = "\\&",
    ["#"] = "\\#",
    ["_"] = "\\_",
    ["%"] = "\\%",
    ["~"] = "\\textasciitilde{}",
    ["^"] = "\\textasciicircum{}",
  }
  local escaped = {}
  for index = 1, #value do
    local character = value:sub(index, index)
    table.insert(escaped, replacements[character] or character)
  end
  return table.concat(escaped)
end

local function transform_code_block(block, generic_label)
  if not FORMAT:match("latex") then
    return nil
  end

  local language = nil
  for _, class in ipairs(block.classes) do
    if class ~= "numberLines" then
      language = language or class
    end
  end

  if not language then
    language = "text"
  end

  language = language:lower()
  local label = generic_languages[language] and generic_label or language_labels[language] or title_case(language)
  local options = {}
  if listings_languages[language] then
    table.insert(options, "language=" .. listings_languages[language])
  end
  local first_number = block.attributes.startFrom
  if first_number and first_number:match("^%d+$") then
    table.insert(options, "firstnumber=" .. first_number)
  end
  local optional = #options > 0 and "[" .. table.concat(options, ",") .. "]" or ""
  return pandoc.RawBlock(
    "latex",
    "\\begin{manualcode}" .. optional .. "{" .. latex_escape(label) .. "}\n" ..
      block.text .. "\n\\end{manualcode}"
  )
end

function Pandoc(document)
  local language = normalized_language(document.meta)
  local configured_label = pandoc.utils.stringify(document.meta["code-block-label"] or "")
  local generic_label = configured_label ~= "" and configured_label or generic_labels[language] or generic_labels.en
  return document:walk({
    CodeBlock = function(block)
      return transform_code_block(block, generic_label)
    end,
  })
end
