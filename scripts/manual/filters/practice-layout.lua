-- Private practice PDFs use their own counters, pagination and image policy.
local assets = {}

local function metadata(meta)
  for original, target in pairs(meta["practice-assets"] or {}) do
    assets[original] = pandoc.utils.stringify(target)
  end
end

local function image(element)
  local target = assets[element.src]
  assert(target, "Undeclared practice image: " .. element.src)
  element.src = target
  return element
end

local function figure(element)
  assert(#element.content == 1 and element.content[1].content
    and #element.content[1].content == 1 and element.content[1].content[1].t == "Image",
    "Practice figures require one standalone image")
  local picture = element.content[1].content[1]
  picture.attributes.width = nil
  picture.attributes.height = nil
  if picture.title ~= "" then
    element.caption.long = pandoc.read(picture.title, "markdown").blocks
  end
  assert(#element.caption.long > 0, "Practice figures require a caption")
  return element
end

local function line_count(text)
  local _, count = text:gsub("\n", "")
  return count + 1
end

local function blocks(values)
  local result = pandoc.List()
  for index, element in ipairs(values) do
    local needed = nil
    if element.t == "Header" then
      needed = 6
      local following = values[index + 1]
      if following and following.t == "Table" then needed = 9 end
      if following and following.t == "CodeBlock" and line_count(following.text) <= 12 then
        needed = line_count(following.text) + 7
      end
    elseif element.t == "CodeBlock" and line_count(element.text) <= 12 then
      needed = line_count(element.text) + 4
    end
    if needed then
      result:insert(pandoc.RawBlock("latex", "\\Needspace{" .. needed .. "\\baselineskip}"))
    end
    result:insert(element)
  end
  return result
end

local function table_widths(element)
  if #element.colspecs < 3 then return nil end
  for _, column in ipairs(element.colspecs) do
    if column[2] and column[2] ~= 0 then return nil end
  end
  local weights, counts, longest = {}, {}, {}
  for index in ipairs(element.colspecs) do weights[index], counts[index], longest[index] = 0, 0, 0 end
  for _, body in ipairs(element.bodies) do
    for _, row in ipairs(body.body) do
      for index, cell in ipairs(row.cells) do
        local text = pandoc.utils.stringify(cell.contents)
        weights[index] = weights[index] + utf8.len(text)
        counts[index] = counts[index] + 1
        for word in text:gmatch("%S+") do longest[index] = math.max(longest[index], utf8.len(word)) end
      end
    end
  end
  local total = 0
  for index in ipairs(weights) do
    weights[index] = math.max(12, longest[index] * 0.9, math.min(90, weights[index] / math.max(1, counts[index]) * 0.65))
    total = total + weights[index]
  end
  for index, weight in ipairs(weights) do element.colspecs[index] = {element.colspecs[index][1], weight / total} end
  return element
end

return {{Meta = metadata}, {Image = image}, {Figure = figure, Table = table_widths}, {Blocks = blocks}}
