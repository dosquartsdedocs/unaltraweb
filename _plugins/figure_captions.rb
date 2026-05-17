# frozen_string_literal: true

require "cgi"

module Unaltraweb
  module FigureCaptions
    module_function

    PANEL_SEQUENCE = ("a".."z").to_a.freeze

    def enabled?(site)
      config = config_for(site)
      config.fetch("enabled", true) != false
    end

    def collections(site)
      config = config_for(site)
      Array(config["collections"] || ["chapters"]).map(&:to_s)
    end

    def config_for(site)
      unaltraweb = site.config["unaltraweb"] || {}
      unaltraweb["figure_captions"] || {}
    end

    def process_collection?(site, label)
      enabled?(site) && collections(site).include?(label.to_s)
    end

    def detect_lang(doc)
      return doc.data["lang"].to_s unless doc.data["lang"].to_s.empty?

      rel = doc.relative_path.to_s.tr("\\", "/")
      parts = rel.split("/")
      parts[1].to_s.empty? ? doc.site.config["default_lang"].to_s : parts[1].to_s
    end

    def label_for(site, lang)
      i18n = site.data["i18n"] || {}
      lang_data = i18n[lang] || i18n[site.config["default_lang"]] || {}
      label = lang_data.dig("figures", "label") if lang_data.respond_to?(:dig)
      label ||= lang_data["figure"]
      label ||= "Figure"
      label.to_s
    end

    def transform_markdown_images(text, lang, label)
      out = +""
      source = text.to_s
      index = 0
      count = 0

      while index < source.length
        if (block = parse_subfigures_block(source, index))
          html, count = subfigures_html(block, lang, label, count)
          out << "\n\n" << html << "\n\n"
          index = block[:end_idx]
          next
        end

        if source[index] == "!" && source[index + 1] == "["
          parsed = parse_markdown_image(source, index)
          if parsed
            alt = parsed[:alt]
            url_and_title = parsed[:url_and_title]
            attrs_raw = parsed[:attrs]
            next_index = parsed[:end_idx]

            if attrs_raw && attrs_raw.match?(/(\.no-figure|data-no-figure\s*=\s*["']true["'])/)
              out << source[index...next_index]
            else
              url, title = split_url_and_title(url_and_title)
              caption = title.to_s.empty? ? alt.to_s : title.to_s
              attrs = kramdown_attrs_to_html(attrs_raw)
              count += 1

              out << "\n\n"
              out << figure_html(
                img: %(<img src="#{h(url.strip)}" alt="#{h(strip_liquid(alt))}"#{attrs.empty? ? "" : " #{attrs}"}>),
                caption: render_inline_markdown(caption),
                label: label,
                lang: lang,
                count: count,
                classes: figure_classes_for(url)
              )
              out << "\n\n"
            end
            index = next_index
            next
          end
        end

        out << source[index]
        index += 1
      end

      out
    end

    def parse_subfigures_block(source, start_index)
      return nil unless line_start?(source, start_index) && source[start_index, 3] == ":::"

      line_end = source.index("\n", start_index) || source.length
      opening = source[start_index...line_end]
      match = opening.match(/\A:::\s*subfigures(?:\s+([^\s"]+))?(?:\s+"([^"]+)")?\s*\z/)
      return nil unless match

      body_start = line_end == source.length ? line_end : line_end + 1
      closing = source.match(/^:::\s*$/m, body_start)
      return nil unless closing

      {
        layout: match[1].to_s,
        caption: match[2].to_s,
        body: source[body_start...closing.begin(0)],
        raw: source[start_index...closing.end(0)],
        end_idx: closing.end(0)
      }
    end

    def line_start?(source, index)
      index.zero? || source[index - 1] == "\n"
    end

    def subfigures_html(block, lang, label, count)
      images = parse_subfigure_images(block[:body])
      return [block[:raw], count] if images.empty?

      count += 1
      rows = subfigure_rows(block[:layout], images.length)
      any_mermaid = images.any? { |img| mermaid_path?(img[:url]) }
      outer_classes = ["md-figure", "md-subfigure-set"]
      outer_classes << "mermaid-figure" if any_mermaid

      row_html = rows.map do |row|
        cells = row.map do |slot|
          image = images[slot[:index]]
          attrs = kramdown_attrs_to_html(image[:attrs])
          caption = render_inline_markdown(image[:caption])
          panel = h(slot[:label])
          %Q{<div class="md-subfigure" data-panel="#{panel}"><img src="#{h(image[:url].strip)}" alt="#{h(strip_liquid(image[:alt]))}"#{attrs.empty? ? "" : " #{attrs}"}>#{caption.to_s.strip.empty? ? "" : %Q{<p class="md-subfigure-caption"><span class="md-subfigure-label">#{panel}.</span> #{caption}</p>}}</div>}
        end.join("\n")
        %Q{<div class="md-subfigure-row" data-count="#{row.length}">\n#{cells}\n</div>}
      end.join("\n")

      clean_caption = render_inline_markdown(block[:caption]).to_s.strip
      figcaption = clean_caption.empty? ? "" : %(<figcaption class="md-figcaption"><span class="figlabel">#{h(label)} #{count}.</span> #{clean_caption}</figcaption>)

      html = <<~HTML.strip
        <figure id="fig-#{h(lang)}-#{count}" class="#{outer_classes.join(' ')}" data-layout="#{h(block[:layout])}">
          <div class="md-figure-inner">
            <div class="md-subfigure-grid">
              #{row_html}
            </div>
          </div>
          #{figcaption}
        </figure>
      HTML

      [html, count]
    end

    def parse_subfigure_images(body)
      images = []
      index = 0
      source = body.to_s

      while index < source.length
        if source[index] == "!" && source[index + 1] == "["
          parsed = parse_markdown_image(source, index)
          if parsed
            url, title = split_url_and_title(parsed[:url_and_title])
            images << {
              alt: parsed[:alt].to_s,
              url: url.to_s,
              caption: title.to_s.empty? ? parsed[:alt].to_s : title.to_s,
              attrs: parsed[:attrs]
            }
            index = parsed[:end_idx]
            next
          end
        end
        index += 1
      end

      images
    end

    def subfigure_rows(layout, image_count)
      used = []
      rows = []
      parsed_rows = layout.to_s.split("/").map { |row| row.split("+").map(&:strip).reject(&:empty?) }.reject(&:empty?)

      parsed_rows.each do |tokens|
        row = []
        tokens.each do |token|
          index = panel_index(token)
          index = next_unused_index(image_count, used) if index.nil? || index >= image_count || used.include?(index)
          next if index.nil?

          used << index
          row << { index: index, label: panel_label(token, index) }
        end
        rows << row if row.any?
      end

      while used.length < image_count
        row = []
        [4, image_count - used.length].min.times do
          index = next_unused_index(image_count, used)
          break if index.nil?

          used << index
          row << { index: index, label: PANEL_SEQUENCE[index] || (index + 1).to_s }
        end
        rows << row if row.any?
      end

      rows
    end

    def panel_index(token)
      value = token.to_s.strip
      return nil if value.empty?
      return value.downcase.ord - "a".ord if value.match?(/\A[a-zA-Z]\z/)
      return value.to_i - 1 if value.match?(/\A\d+\z/)

      nil
    end

    def panel_label(token, index)
      value = token.to_s.strip
      return value.downcase if value.match?(/\A[a-zA-Z]\z/)

      PANEL_SEQUENCE[index] || (index + 1).to_s
    end

    def next_unused_index(image_count, used)
      (0...image_count).find { |candidate| !used.include?(candidate) }
    end

    def parse_markdown_image(source, start_index)
      index = start_index + 2
      alt, index = read_balanced(source, index, "[", "]")
      return nil unless alt && source[index - 1] == "]" && source[index] == "("

      index += 1
      url_and_title, index = read_until_closing_paren(source, index)
      return nil unless url_and_title && source[index] == ")"

      index += 1
      index = skip_spaces(source, index)

      attrs_raw = nil
      if source[index] == "{"
        close_index = source.index("}", index)
        return nil unless close_index

        attrs_raw = source[index..close_index].sub(/\A\{:\s*/, "{").strip
        index = close_index + 1
      end

      { alt: alt, url_and_title: url_and_title, attrs: attrs_raw, end_idx: index }
    end

    def read_balanced(source, index, open_char, close_char)
      depth = 1
      start = index
      while index < source.length
        char = source[index]
        if char == "\\"
          index += 2
          next
        elsif char == open_char
          depth += 1
        elsif char == close_char
          depth -= 1
          return [source[start...index], index + 1] if depth.zero?
        end
        index += 1
      end
      [nil, index]
    end

    def read_until_closing_paren(source, index)
      depth = 1
      start = index
      while index < source.length
        char = source[index]
        if char == "\\"
          index += 2
          next
        elsif char == "("
          depth += 1
        elsif char == ")"
          depth -= 1
          return [source[start...index], index] if depth.zero?
        end
        index += 1
      end
      [nil, index]
    end

    def skip_spaces(source, index)
      index += 1 while index < source.length && source[index] =~ /\s/
      index
    end

    def split_url_and_title(value)
      text = value.to_s.strip
      if text =~ /\s+["“]([^"”]+)["”]\s*\z/m
        title = Regexp.last_match(1).strip
        url = text.sub(/\s+["“][^"”]+["”]\s*\z/m, "").strip
        [url, title]
      elsif text =~ /\s+['‘]([^'’]+)['’]\s*\z/m
        title = Regexp.last_match(1).strip
        url = text.sub(/\s+['‘][^'’]+['’]\s*\z/m, "").strip
        [url, title]
      else
        [text, nil]
      end
    end

    def wrap_html_images(output, lang, label)
      return output unless output.to_s.include?("<img")

      count = output.scan(/<figure\b/i).size
      output.gsub(%r{<p>\s*(<img\b[^>]*>)\s*</p>}mi) do
        img_tag = Regexp.last_match(1)
        next Regexp.last_match(0) if img_tag =~ /\bdata-no-figure\s*=\s*["']true["']/i

        caption = extract_attr(img_tag, "title").to_s
        caption = extract_attr(img_tag, "alt").to_s if caption.empty?
        count += 1

        figure_html(
          img: img_tag,
          caption: render_inline_markdown(CGI.unescapeHTML(caption)),
          label: label,
          lang: lang,
          count: count,
          classes: figure_classes_for(extract_attr(img_tag, "src"))
        )
      end
    end

    def figure_html(img:, caption:, label:, lang:, count:, classes: ["md-figure"])
      classes = Array(classes)
      classes = ["md-figure"] if classes.empty?
      clean_caption = caption.to_s.strip
      figcaption = if clean_caption.empty?
        ""
      else
        %(<figcaption class="md-figcaption"><span class="figlabel">#{h(label)} #{count}.</span> #{clean_caption}</figcaption>)
      end

      <<~HTML.strip
        <figure id="fig-#{h(lang)}-#{count}" class="#{classes.map { |klass| h(klass) }.join(' ')}">
          <div class="md-figure-inner">#{img}</div>
          #{figcaption}
        </figure>
      HTML
    end

    def figure_classes_for(path)
      classes = ["md-figure"]
      classes << "mermaid-figure" if mermaid_path?(path)
      classes
    end

    def mermaid_path?(path)
      path.to_s.match?(/\.mmd(?:\.edited)?\.svg(?:[?#].*)?\z/i) || path.to_s.match?(/\.mmd(?:[?#].*)?\z/i)
    end

    def render_inline_markdown(text)
      html = text.to_s.dup
      html.gsub!(/\[([^\]]+)\]\((\S+?)(?:\s+"([^"]*)")?\)/) do
        label = Regexp.last_match(1)
        url = Regexp.last_match(2)
        title = Regexp.last_match(3)
        title_attr = title.to_s.empty? ? "" : %( title="#{h(title)}")
        %(<a href="#{h(url)}"#{title_attr}>#{label}</a>)
      end
      html.gsub!(/\*\*([^*]+)\*\*/, '<strong>\1</strong>')
      html.gsub!(/\*([^*]+)\*/, '<em>\1</em>')
      html
    end

    def extract_attr(tag, name)
      tag[/\b#{Regexp.escape(name)}="([^"]*)"/i, 1] || tag[/\b#{Regexp.escape(name)}='([^']*)'/i, 1]
    end

    def strip_liquid(value)
      value.to_s.gsub(/\{%.*?%\}/m, "").gsub(/\{\{.*?\}\}/m, "").strip
    end

    def h(value)
      value.to_s.gsub("&", "&amp;").gsub("<", "&lt;").gsub(">", "&gt;").gsub('"', "&quot;")
    end

    def kramdown_attrs_to_html(raw)
      return "" if raw.to_s.strip.empty?

      source = raw.to_s.strip.sub(/\A\{:\s*/, "").sub(/\A\{\s*/, "").sub(/\s*\}\z/, "")
      return "" if source.empty?

      source = source.tr("“”’‘", %q{""''})
      classes = []
      id = nil
      other = []
      source.scan(/(?:[^\s"']+|"(?:\\.|[^"])*"|'(?:\\.|[^'])*')+/).each do |token|
        if token.start_with?(".")
          classes << token[1..]
        elsif token.start_with?("#")
          id = token[1..]
        else
          other << token
        end
      end

      attrs = []
      attrs << %(id="#{h(id)}") if id && !id.empty?
      attrs << %(class="#{h(classes.join(" "))}") if classes.any?
      attrs.concat(other)
      attrs.join(" ")
    end
  end
end

class UnaltrawebFigureCaptionGenerator < Jekyll::Generator
  safe true
  priority :low

  def generate(site)
    return unless Unaltraweb::FigureCaptions.enabled?(site)

    Unaltraweb::FigureCaptions.collections(site).each do |collection_label|
      collection = site.collections[collection_label]
      next unless collection

      collection.docs.each do |doc|
        lang = Unaltraweb::FigureCaptions.detect_lang(doc)
        label = Unaltraweb::FigureCaptions.label_for(site, lang)
        doc.content = Unaltraweb::FigureCaptions.transform_markdown_images(doc.content, lang, label)
      end
    end
  end
end

Jekyll::Hooks.register :documents, :post_render do |doc|
  next unless doc.collection && Unaltraweb::FigureCaptions.process_collection?(doc.site, doc.collection.label)

  lang = Unaltraweb::FigureCaptions.detect_lang(doc)
  label = Unaltraweb::FigureCaptions.label_for(doc.site, lang)
  doc.output = Unaltraweb::FigureCaptions.wrap_html_images(doc.output, lang, label)
end
