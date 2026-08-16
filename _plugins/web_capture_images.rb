# frozen_string_literal: true

require "rexml/document"

module Unaltraweb
  module WebCaptureImages
    module_function

    BASEURL_PREFIX = /\A\{\{\s*site\.baseurl\s*\}\}/.freeze
    REMOTE_PATH_PREFIX = %r{\A(?:[a-z]+:)?//}i.freeze
    FENCED_CODE_BLOCK = /^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$/m.freeze
    CAPTURE_SOURCE = /\.capture\.ya?ml/i.freeze
    ALLOWED_ELEMENTS = %w[svg g defs metadata title desc image rect path text tspan marker polygon polyline line circle ellipse clippath mask lineargradient radialgradient stop pattern use namedview grid page].freeze
    ALLOWED_ATTRIBUTES = %w[id class version baseprofile xmlns xlink inkscape x y x1 y1 x2 y2 cx cy r rx ry width height viewbox preserveaspectratio d points transform fill stroke stroke-width stroke-linecap stroke-linejoin stroke-miterlimit stroke-dasharray stroke-dashoffset opacity fill-opacity stroke-opacity fill-rule clip-rule clip-path mask font-family font-size font-style font-weight text-anchor dominant-baseline marker-start marker-mid marker-end markerwidth markerheight refx refy orient offset stop-color stop-opacity patternunits patterncontentunits gradientunits gradienttransform spreadmethod href style data-selector groupmode label space role aria-label pagecolor bordercolor borderopacity objecttolerance gridtolerance guidetolerance showgrid showguides zoom current-layer document-units pagecheckerboard deskcolor units originx originy spacingx spacingy].freeze
    ALLOWED_STYLE_PROPERTIES = %w[fill stroke stroke-width stroke-linecap stroke-linejoin stroke-miterlimit stroke-dasharray stroke-dashoffset opacity fill-opacity stroke-opacity fill-rule clip-rule clip-path mask font-family font-size font-style font-weight text-anchor dominant-baseline marker-start marker-mid marker-end stop-color stop-opacity display visibility].freeze

    def rewrite(content, site_source:)
      return content if content.nil? || content.empty?

      rewrite_outside_code_fences(content) { |chunk| rewrite_chunk(chunk, site_source: site_source) }
    end

    def rewrite_chunk(content, site_source:)
      out = content.dup
      out.gsub!(/!\[([^\]]*)\]\(([^)]*?#{CAPTURE_SOURCE})(\s+"[^"]*")?\)/i) do
        alt = Regexp.last_match(1)
        path = svg_path_for(Regexp.last_match(2), site_source)
        title = Regexp.last_match(3).to_s
        "![#{alt}](#{path}#{title})"
      end
      out.gsub!(/(<img\b[^>]*\bsrc=)(["'])([^"']+?#{CAPTURE_SOURCE})\2/i) do
        prefix = Regexp.last_match(1)
        quote = Regexp.last_match(2)
        path = svg_path_for(Regexp.last_match(3), site_source)
        "#{prefix}#{quote}#{path}#{quote}"
      end
      out
    end

    def rewrite_outside_code_fences(content)
      source = content.to_s
      fences = []
      protected_source = source.gsub(FENCED_CODE_BLOCK) do
        token = "UNALTRAWEBWEBFENCEDCODEBLOCK#{fences.length}"
        fences << Regexp.last_match(0)
        token
      end
      transformed = yield(protected_source)
      fences.each_index.reverse_each do |index|
        transformed.gsub!("UNALTRAWEBWEBFENCEDCODEBLOCK#{index}", fences[index])
      end
      transformed
    end

    def svg_path_for(capture_path, site_source)
      edited = capture_path.sub(/\.capture\.ya?ml/i, ".capture.edited.svg")
      if local_asset_exists?(edited, site_source)
        validate_svg!(local_asset_path(edited, site_source))
        return edited
      end

      generated = capture_path.sub(/\.capture\.ya?ml/i, ".capture.svg")
      local = local_asset_path(generated, site_source)
      unless local && File.file?(local)
        raise Jekyll::Errors::FatalException, "Missing rendered web capture SVG for #{capture_path}. Run make web-capture-render."
      end
      validate_svg!(local)
      generated
    end

    def validate_svg!(path)
      text = File.read(path, encoding: "UTF-8")
      lowered = text.downcase
      raise "unsafe XML declaration" if lowered.include?("<!doctype") || lowered.include?("<!entity")

      document = REXML::Document.new(text)
      document.elements.each("//*") do |element|
        tag = element.name.to_s.downcase
        raise "unsupported element #{tag}" unless ALLOWED_ELEMENTS.include?(tag)

        element.attributes.each_attribute do |attribute|
          name = attribute.expanded_name.to_s.split(":").last.downcase
          value = attribute.value.to_s.strip
          lowered_value = value.downcase
          raise "unsupported attribute #{name}" unless ALLOWED_ATTRIBUTES.include?(name)
          raise "unsafe attribute #{name}" if lowered_value.include?("@import") || lowered_value.include?("javascript:") || lowered_value.include?("expression(")
          if name == "href" && !value.start_with?("data:image/png;base64,", "#")
            raise "external SVG reference"
          end
          without_local_urls = lowered_value.gsub(/url\(\s*["']?#[A-Za-z_][-:.A-Za-z0-9_]*["']?\s*\)/, "")
          if without_local_urls.include?("url(")
            raise "external CSS reference"
          end
          if name == "style"
            value.split(";").map(&:strip).reject(&:empty?).each do |declaration|
              property, separator, = declaration.partition(":")
              raise "unsupported style #{property.strip}" if separator.empty? || !ALLOWED_STYLE_PROPERTIES.include?(property.strip.downcase)
            end
          end
        end
      end
    rescue REXML::ParseException, RuntimeError => e
      raise Jekyll::Errors::FatalException, "Unsafe web capture SVG #{path}: #{e.message}"
    end

    def local_asset_exists?(asset_path, site_source)
      local = local_asset_path(asset_path, site_source)
      local && File.file?(local)
    end

    def local_asset_path(asset_path, site_source)
      local_path = asset_path
        .sub(BASEURL_PREFIX, "")
        .split(/[?#]/, 2)
        .first.to_s
        .sub(%r{\A/+}, "")
      return nil if local_path.empty? || local_path.match?(REMOTE_PATH_PREFIX)

      root = File.expand_path(site_source)
      path = File.expand_path(local_path, root)
      return nil unless path == root || path.start_with?("#{root}/")

      path
    end

    Jekyll::Hooks.register :site, :post_read do |site|
      site.static_files.reject! do |file|
        relative = file.relative_path.to_s.downcase
        if relative.end_with?(".capture.svg")
          source = file.path.sub(/\.capture\.svg\z/i, ".capture.yml")
          source_yaml = file.path.sub(/\.capture\.svg\z/i, ".capture.yaml")
          edited = file.path.sub(/\.capture\.svg\z/i, ".capture.edited.svg")
          remove = (!File.file?(source) && !File.file?(source_yaml)) || File.file?(edited)
          validate_svg!(file.path) unless remove
          remove
        elsif relative.end_with?(".capture.edited.svg")
          source = file.path.sub(/\.capture\.edited\.svg\z/i, ".capture.yml")
          source_yaml = file.path.sub(/\.capture\.edited\.svg\z/i, ".capture.yaml")
          remove = !File.file?(source) && !File.file?(source_yaml)
          validate_svg!(file.path) unless remove
          remove
        else
          relative.end_with?(".capture.yml", ".capture.yaml", ".capture.png")
        end
      end
    end
  end
end

Jekyll::Hooks.register [:documents, :pages], :pre_render do |doc|
  next unless doc.respond_to?(:content) && doc.content

  doc.content = Unaltraweb::WebCaptureImages.rewrite(doc.content, site_source: doc.site.source)
end if defined?(Jekyll::Hooks)
