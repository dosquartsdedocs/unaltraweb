# frozen_string_literal: true

require "cgi"
require "json"
require "open3"
require "timeout"

module UnaltrawebRetainedDocuments
  def self.verify(site, output = nil)
    return { "imports" => [] } unless File.exist?(File.join(site.source, ".unaltraweb", "artifacts"))

    source = File.expand_path("../src", __dir__)
    command = ["python3", "-m", "unaltraweb_mcp.artifact_imports", "--project", File.expand_path(site.source)]
    command += ["--output-folder", output] if output
    stdout, stderr, status = Timeout.timeout(120) { Open3.capture3({ "PYTHONPATH" => source }, *command) }
    result = JSON.parse(stdout)
    raise Jekyll::Errors::FatalException, "Retained document check failed: #{result['error'] || stderr}" unless status.success? && result["ok"] == true

    result
  end

  class Generator < Jekyll::Generator
    safe true
    priority :highest

    def generate(site)
      site.config["unaltraweb_retained_documents"] = UnaltrawebRetainedDocuments.verify(site)["imports"].to_h { |item| [item["id"], item] }
    end
  end

  class DocumentTag < Liquid::Tag
    def initialize(name, markup, tokens)
      super
      @id = markup.strip
      raise ArgumentError, "retained_document requires one import ID" unless @id.match?(/\A[a-z][a-z0-9-]{0,63}\z/)
    end

    def render(context)
      site = context.registers[:site]
      item = (site.config["unaltraweb_retained_documents"] || {})[@id]
      raise Jekyll::Errors::FatalException, "Unverified retained document #{@id}" unless item

      path = site.config["baseurl"].to_s.sub(%r{/\z}, "") + "/" + item.fetch("pdf")
      url = CGI.escapeHTML(path)
      page = context["page"]
      title = CGI.escapeHTML(((page && page["title"]) || @id).to_s)
      %(<figure class="retained-document"><object data-retained-document="#{@id}" data="#{url}" type="application/pdf" aria-label="#{title}" style="width:100%;height:70vh"><a href="#{url}">#{title}</a></object><figcaption><a href="#{url}">#{title} (PDF)</a></figcaption></figure>)
    end
  end
end

Liquid::Template.register_tag("retained_document", UnaltrawebRetainedDocuments::DocumentTag)

Jekyll::Hooks.register :site, :post_write do |site|
  source = File.expand_path(site.source)
  destination = File.expand_path(site.dest)
  if destination.start_with?(source + "/")
    UnaltrawebRetainedDocuments.verify(site, destination.delete_prefix(source + "/"))
  elsif !(site.config["unaltraweb_retained_documents"] || {}).empty?
    raise Jekyll::Errors::FatalException, "Retained documents require a project-confined site destination"
  end
end
