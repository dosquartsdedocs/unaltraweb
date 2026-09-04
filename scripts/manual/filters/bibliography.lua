local references = {}
local sort_keys = {}
local access = {}

local function has_class(div, expected)
  for _, class in ipairs(div.classes) do
    if class == expected then
      return true
    end
  end
  return false
end

local function fold(value)
  local lower = pandoc.text and pandoc.text.lower or string.lower
  value = lower(value)
  local replacements = {
    ["à"] = "a", ["á"] = "a", ["â"] = "a", ["ä"] = "a", ["ã"] = "a", ["å"] = "a",
    ["ç"] = "c", ["è"] = "e", ["é"] = "e", ["ê"] = "e", ["ë"] = "e",
    ["ì"] = "i", ["í"] = "i", ["î"] = "i", ["ï"] = "i", ["ñ"] = "n",
    ["ò"] = "o", ["ó"] = "o", ["ô"] = "o", ["ö"] = "o", ["õ"] = "o",
    ["ù"] = "u", ["ú"] = "u", ["û"] = "u", ["ü"] = "u", ["ý"] = "y", ["ÿ"] = "y"
  }
  for source, replacement in pairs(replacements) do
    value = value:gsub(source, replacement)
  end
  return value:gsub("%s+", " ")
end

local function sort_references(items)
  table.sort(items, function(left, right)
    local left_text = pandoc.utils.stringify(left)
    local right_text = pandoc.utils.stringify(right)
    local left_id = left.identifier:match("^ref%-(.+)$")
    local right_id = right.identifier:match("^ref%-(.+)$")
    local left_key = sort_keys[left_id] or fold(left_text)
    local right_key = sort_keys[right_id] or fold(right_text)
    if left_key == right_key then
      return left_text < right_text
    end
    return left_key < right_key
  end)
end

local function append_link(entry, label, target)
  local link = pandoc.Link(label, target)
  local block = entry.content[#entry.content]
  if block and (block.t == "Para" or block.t == "Plain") then
    table.insert(block.content, pandoc.Space())
    table.insert(block.content, link)
  else
    table.insert(entry.content, pandoc.Para({link}))
  end
end

local function ensure_access(entry, key)
  local values = access[key]
  if not values then
    return
  end
  local rendered = pandoc.utils.stringify(entry)
  local doi = values.doi or ""
  if doi ~= "" then
    doi = doi:gsub("^[Dd][Oo][Ii]:%s*", "")
    doi = doi:gsub("^https?://[Dd][Xx]%.[Dd][Oo][Ii]%.org/", "")
    doi = doi:gsub("^https?://[Dd][Oo][Ii]%.org/", "")
    if not rendered:find(doi, 1, true) then
      local doi_url = "https://doi.org/" .. doi
      append_link(entry, doi_url, doi_url)
      rendered = rendered .. " " .. doi_url
    end
  end
  for _, url in ipairs(values.urls or {}) do
    if url ~= "" and not rendered:find(url, 1, true) then
      append_link(entry, url, url)
      rendered = rendered .. " " .. url
    end
  end
end

local function without_identifier(entry)
  return pandoc.Div(entry.content, pandoc.Attr("", entry.classes, entry.attributes))
end

function Pandoc(document)
  references = {}
  sort_keys = {}
  access = {}
  for key, value in pairs(document.meta["bibliography-sort-keys"] or {}) do
    sort_keys[key] = pandoc.utils.stringify(value)
  end
  for key, value in pairs(document.meta["bibliography-access"] or {}) do
    access[key] = {
      doi = pandoc.utils.stringify(value.doi or ""),
      urls = {}
    }
    for _, url in ipairs(value.urls or {}) do
      table.insert(access[key].urls, pandoc.utils.stringify(url))
    end
  end

  document = document:walk({
    Div = function(div)
      if div.identifier ~= "refs" then
        return nil
      end

      local sorted = {}
      for _, block in ipairs(div.content) do
        if block.t == "Div" and block.identifier:match("^ref%-") then
          local key = block.identifier:sub(5)
          ensure_access(block, key)
          references[key] = block
          table.insert(sorted, block)
        end
      end
      sort_references(sorted)

      local index = 1
      for position, block in ipairs(div.content) do
        if block.t == "Div" and block.identifier:match("^ref%-") then
          div.content[position] = sorted[index]
          index = index + 1
        end
      end
      return div
    end
  })

  local heading = "References"
  if document.meta["chapter-references-title"] then
    heading = pandoc.utils.stringify(document.meta["chapter-references-title"])
  end

  document = document:walk({
    Div = function(div)
      if not has_class(div, "manual-chapter-citations") then
        return nil
      end

      local selected = {}
      local keys = div.attributes["data-citations"] or ""
      for key in keys:gmatch("[^,]+") do
        if references[key] then
          table.insert(selected, references[key])
        end
      end
      if #selected == 0 then
        return {}
      end

      sort_references(selected)
      for index, entry in ipairs(selected) do
        selected[index] = without_identifier(entry)
      end
      return {
        pandoc.Header(2, heading, pandoc.Attr("", {"unnumbered", "unlisted"})),
        pandoc.Div(selected, pandoc.Attr("", {"references", "manual-chapter-references"}))
      }
    end
  })

  return document
end
