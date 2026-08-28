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
  local classes = {}
  local numbered = false
  for _, class in ipairs(block.classes) do
    if class == "numberLines" then
      numbered = true
      table.insert(classes, class)
    else
      table.insert(classes, class)
      language = language or class
    end
  end

  if not language then
    language = "text"
    table.insert(classes, 1, language)
  end
  if not numbered then
    table.insert(classes, "numberLines")
  end

  language = language:lower()
  local label = generic_languages[language] and generic_label or language_labels[language] or title_case(language)
  local decorated = pandoc.CodeBlock(block.text, pandoc.Attr(block.identifier, classes, block.attributes))
  return {
    pandoc.RawBlock("latex", "\\begin{manualcode}{" .. latex_escape(label) .. "}"),
    decorated,
    pandoc.RawBlock("latex", "\\end{manualcode}"),
  }
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
