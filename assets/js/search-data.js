// get the ninja-keys element
const ninja = document.querySelector('ninja-keys');

// add the home and posts menu items
ninja.data = [{
      id: "nav-home",
      title: "Home",
      section: "Navigation",
      handler: () => {
        window.location.href = "/unaltraweb/en/";
      },
    },{id: "dropdown-the-project",
              title: "The project",
              description: "",
              section: "Dropdown",
              handler: () => {
                window.location.href = "/unaltraweb/en/the-project/";
              },
            },{id: "dropdown-former-projects",
              title: "Former projects",
              description: "",
              section: "Dropdown",
              handler: () => {
                window.location.href = "/unaltraweb/en/former-projects/";
              },
            },{id: "dropdown-el-proyecto",
              title: "El proyecto",
              description: "",
              section: "Dropdown",
              handler: () => {
                window.location.href = "/unaltraweb/es/el-proyecto/";
              },
            },{id: "dropdown-proyectos-previos",
              title: "Proyectos previos",
              description: "",
              section: "Dropdown",
              handler: () => {
                window.location.href = "/unaltraweb/es/proyectos-previos/";
              },
            },{id: "dropdown-el-projecte",
              title: "El projecte",
              description: "",
              section: "Dropdown",
              handler: () => {
                window.location.href = "/unaltraweb/ca/el-projecte/";
              },
            },{id: "dropdown-projectes-anteriors",
              title: "Projectes anteriors",
              description: "",
              section: "Dropdown",
              handler: () => {
                window.location.href = "/unaltraweb/ca/projectes-anteriors/";
              },
            },{id: "nav-equip",
          title: "Equip",
          description: "",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/ca/equip/";
          },
        },{id: "nav-equipo",
          title: "Equipo",
          description: "",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/es/equipo/";
          },
        },{id: "nav-team",
          title: "Team",
          description: "",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/en/team/";
          },
        },{id: "nav-publicaciones",
          title: "Publicaciones",
          description: "Resultados científicos e informes técnicos.",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/es/publicaciones/";
          },
        },{id: "nav-publicacions",
          title: "Publicacions",
          description: "Resultats científics i informes tècnics.",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/ca/publicacions/";
          },
        },{id: "nav-publications",
          title: "Publications",
          description: "Scientific outputs and technical reports.",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/en/publications/";
          },
        },{id: "nav-tesis",
          title: "Tesis",
          description: "Tesis doctorales en curso o finalizadas.",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/es/tesis/";
          },
        },{id: "nav-tesis",
          title: "Tesis",
          description: "Tesis doctorals en curs o finalitzades.",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/ca/tesis/";
          },
        },{id: "nav-theses",
          title: "Theses",
          description: "Ongoing or completed PhD theses.",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/en/theses/";
          },
        },{id: "nav-theses",
          title: "Theses",
          description: "Ongoing or already finished PhD theses.",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/theses/";
          },
        },{id: "nav-bookshelf",
          title: "Bookshelf",
          description: "",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/books/";
          },
        },{id: "dropdown-productos",
              title: "Productos",
              description: "",
              section: "Dropdown",
              handler: () => {
                window.location.href = "/unaltraweb/es/productos/";
              },
            },{id: "dropdown-repositorios",
              title: "Repositorios",
              description: "",
              section: "Dropdown",
              handler: () => {
                window.location.href = "/unaltraweb/es/repositorios/";
              },
            },{id: "dropdown-productes",
              title: "Productes",
              description: "",
              section: "Dropdown",
              handler: () => {
                window.location.href = "/unaltraweb/ca/productes/";
              },
            },{id: "dropdown-repositoris",
              title: "Repositoris",
              description: "",
              section: "Dropdown",
              handler: () => {
                window.location.href = "/unaltraweb/ca/repositoris/";
              },
            },{id: "dropdown-outputs",
              title: "Outputs",
              description: "",
              section: "Dropdown",
              handler: () => {
                window.location.href = "/unaltraweb/en/outputs/";
              },
            },{id: "dropdown-repositories",
              title: "Repositories",
              description: "",
              section: "Dropdown",
              handler: () => {
                window.location.href = "/unaltraweb/en/repositories/";
              },
            },{id: "dropdown-blog",
              title: "Blog",
              description: "",
              section: "Dropdown",
              handler: () => {
                window.location.href = "/unaltraweb/en/blog/";
              },
            },{id: "dropdown-reading",
              title: "Reading",
              description: "",
              section: "Dropdown",
              handler: () => {
                window.location.href = "/unaltraweb/en/book-reviews/";
              },
            },{id: "dropdown-blog",
              title: "Blog",
              description: "",
              section: "Dropdown",
              handler: () => {
                window.location.href = "/unaltraweb/es/blog/";
              },
            },{id: "dropdown-lecturas",
              title: "Lecturas",
              description: "",
              section: "Dropdown",
              handler: () => {
                window.location.href = "/unaltraweb/es/resenas-libros/";
              },
            },{id: "dropdown-blog",
              title: "Blog",
              description: "",
              section: "Dropdown",
              handler: () => {
                window.location.href = "/unaltraweb/ca/blog/";
              },
            },{id: "dropdown-lectures",
              title: "Lectures",
              description: "",
              section: "Dropdown",
              handler: () => {
                window.location.href = "/unaltraweb/ca/ressenyes-llibres/";
              },
            },{id: "nav-cv",
          title: "CV",
          description: "This is a description of the page. You can modify it in &#39;_pages/cv.md&#39;. You can also change or remove the top pdf download button.",
          section: "Navigation",
          handler: () => {
            window.location.href = "/unaltraweb/cv/";
          },
        },{id: "post-actualització-de-plantilla-per-a-webs-de-projecte",
        
          title: "Actualització de plantilla per a webs de projecte",
        
        description: "Entrada de mostra per documentar avenços i canvis metodològics del projecte.",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/ca/blog/2026/actualitzacio-plantilla-projecte/";
          
        },
      },{id: "post-actualización-de-plantilla-para-webs-de-proyecto",
        
          title: "Actualización de plantilla para webs de proyecto",
        
        description: "Entrada de ejemplo para documentar avances y cambios metodológicos del proyecto.",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/es/blog/2026/actualizacion-plantilla-proyecto/";
          
        },
      },{id: "post-a-post-with-plotly-js",
        
          title: "a post with plotly.js",
        
        description: "this is what included plotly.js code could look like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2025/plotly/";
          
        },
      },{id: "post-a-post-with-image-galleries",
        
          title: "a post with image galleries",
        
        description: "this is what included image galleries could look like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2024/photo-gallery/";
          
        },
      },{id: "post-a-post-with-tabs",
        
          title: "a post with tabs",
        
        description: "this is what included tabs in a post could look like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2024/tabs/";
          
        },
      },{id: "post-a-post-with-typograms",
        
          title: "a post with typograms",
        
        description: "this is what included typograms code could look like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2024/typograms/";
          
        },
      },{id: "post-a-post-that-can-be-cited",
        
          title: "a post that can be cited",
        
        description: "this is what a post that can be cited looks like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2024/post-citation/";
          
        },
      },{id: "post-a-post-with-pseudo-code",
        
          title: "a post with pseudo code",
        
        description: "this is what included pseudo code could look like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2024/pseudocode/";
          
        },
      },{id: "post-a-post-with-code-diff",
        
          title: "a post with code diff",
        
        description: "this is how you can display code diffs",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2024/code-diff/";
          
        },
      },{id: "post-a-post-with-advanced-image-components",
        
          title: "a post with advanced image components",
        
        description: "this is what advanced image components could look like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2024/advanced-images/";
          
        },
      },{id: "post-a-post-with-vega-lite",
        
          title: "a post with vega lite",
        
        description: "this is what included vega lite code could look like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2024/vega-lite/";
          
        },
      },{id: "post-a-post-with-geojson",
        
          title: "a post with geojson",
        
        description: "this is what included geojson code could look like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2024/geojson-map/";
          
        },
      },{id: "post-a-post-with-echarts",
        
          title: "a post with echarts",
        
        description: "this is what included echarts code could look like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2024/echarts/";
          
        },
      },{id: "post-a-post-with-chart-js",
        
          title: "a post with chart.js",
        
        description: "this is what included chart.js code could look like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2024/chartjs/";
          
        },
      },{id: "post-a-post-with-tikzjax",
        
          title: "a post with TikZJax",
        
        description: "this is what included TikZ code could look like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2023/tikzjax/";
          
        },
      },{id: "post-a-post-with-bibliography",
        
          title: "a post with bibliography",
        
        description: "an example of a blog post with bibliography",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2023/post-bibliography/";
          
        },
      },{id: "post-a-post-with-jupyter-notebook",
        
          title: "a post with jupyter notebook",
        
        description: "an example of a blog post with jupyter notebook",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2023/jupyter-notebook/";
          
        },
      },{id: "post-a-post-with-custom-blockquotes",
        
          title: "a post with custom blockquotes",
        
        description: "an example of a blog post with custom blockquotes",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2023/custom-blockquotes/";
          
        },
      },{id: "post-a-post-with-table-of-contents-on-a-sidebar",
        
          title: "a post with table of contents on a sidebar",
        
        description: "an example of a blog post with table of contents on a sidebar",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2023/sidebar-table-of-contents/";
          
        },
      },{id: "post-a-post-with-audios",
        
          title: "a post with audios",
        
        description: "this is what included audios could look like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2023/audios/";
          
        },
      },{id: "post-a-post-with-videos",
        
          title: "a post with videos",
        
        description: "this is what included videos could look like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2023/videos/";
          
        },
      },{id: "post-displaying-beautiful-tables-with-bootstrap-tables",
        
          title: "displaying beautiful tables with Bootstrap Tables",
        
        description: "an example of how to use Bootstrap Tables",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2023/tables/";
          
        },
      },{id: "post-a-post-with-table-of-contents",
        
          title: "a post with table of contents",
        
        description: "an example of a blog post with table of contents",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2023/table-of-contents/";
          
        },
      },{id: "post-a-post-with-giscus-comments",
        
          title: "a post with giscus comments",
        
        description: "an example of a blog post with giscus comments",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2022/giscus-comments/";
          
        },
      },{id: "post-a-post-with-redirect",
        
          title: "a post with redirect",
        
        description: "you can also redirect to assets like pdf",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/assets/pdf/example_pdf.pdf";
          
        },
      },{id: "post-a-post-with-diagrams",
        
          title: "a post with diagrams",
        
        description: "an example of a blog post with diagrams",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2021/diagrams/";
          
        },
      },{id: "post-a-distill-style-blog-post",
        
          title: "a distill-style blog post",
        
        description: "an example of a distill-style blog post and main elements",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2021/distill/";
          
        },
      },{id: "post-a-post-with-twitter",
        
          title: "a post with twitter",
        
        description: "an example of a blog post with twitter",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2020/twitter/";
          
        },
      },{id: "post-a-post-with-disqus-comments",
        
          title: "a post with disqus comments",
        
        description: "an example of a blog post with disqus comments",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2015/disqus-comments/";
          
        },
      },{id: "post-a-post-with-math",
        
          title: "a post with math",
        
        description: "an example of a blog post with some math",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2015/math/";
          
        },
      },{id: "post-a-post-with-code",
        
          title: "a post with code",
        
        description: "an example of a blog post with some code",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2015/code/";
          
        },
      },{id: "post-a-post-with-images",
        
          title: "a post with images",
        
        description: "this is what included images could look like",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2015/images/";
          
        },
      },{id: "post-a-post-with-formatting-and-links",
        
          title: "a post with formatting and links",
        
        description: "march &amp; april, looking forward to summer",
        section: "Posts",
        handler: () => {
          
            window.location.href = "/unaltraweb/blog/2015/formatting-and-links/";
          
        },
      },{id: "books-parcs-temàtics-el-paper-de-l-39-oci-en-la-construcció-social-de-l-39-espai",
          title: 'Parcs temàtics: el paper de l&amp;#39;oci en la construcció social de l&amp;#39;espai',
          description: "",
          section: "Books",handler: () => {
              window.location.href = "/unaltraweb/ca/ressenyes-llibres/parcs-tematics-i-turisme/";
            },},{id: "books-theme-parks-leisure-and-the-social-construction-of-space",
          title: 'Theme Parks: Leisure and the Social Construction of Space',
          description: "",
          section: "Books",handler: () => {
              window.location.href = "/unaltraweb/en/book-reviews/theme-parks-and-tourism/";
            },},{id: "books-parques-temáticos-el-papel-del-ocio-en-la-construcción-social-del-espacio",
          title: 'Parques temáticos: el papel del ocio en la construcción social del espacio',
          description: "",
          section: "Books",handler: () => {
              window.location.href = "/unaltraweb/es/resenas-libros/parques-tematicos-y-turismo/";
            },},{id: "books-geografia-d-39-europa",
          title: 'Geografia d&amp;#39;Europa',
          description: "",
          section: "Books",handler: () => {
              window.location.href = "/unaltraweb/ca/ressenyes-llibres/geografia-ue-manual/";
            },},{id: "books-geography-of-europe",
          title: 'Geography of Europe',
          description: "",
          section: "Books",handler: () => {
              window.location.href = "/unaltraweb/en/book-reviews/geography-eu-manual/";
            },},{id: "books-geografía-de-europa",
          title: 'Geografía de Europa',
          description: "",
          section: "Books",handler: () => {
              window.location.href = "/unaltraweb/es/resenas-libros/geografia-ue-manual/";
            },},{id: "news-a-simple-inline-announcement",
          title: 'A simple inline announcement.',
          description: "",
          section: "News",},{id: "news-a-long-announcement-with-details",
          title: 'A long announcement with details',
          description: "",
          section: "News",handler: () => {
              window.location.href = "/unaltraweb/news/announcement_2/";
            },},{id: "news-a-simple-inline-announcement-with-markdown-emoji-sparkles-smile",
          title: 'A simple inline announcement with Markdown emoji! :sparkles: :smile:',
          description: "",
          section: "News",},{id: "news-publicada-la-versión-base-de-la-plantilla-multilingüe-del-proyecto-es-ca-en-con-estructura-de-productos-publicaciones-y-equipo",
          title: 'Publicada la versión base de la plantilla multilingüe del proyecto (ES/CA/EN) con estructura...',
          description: "",
          section: "News",},{id: "news-publicada-la-versió-base-de-la-plantilla-multilingüe-del-projecte-es-ca-en-amb-estructura-de-productes-publicacions-i-equip",
          title: 'Publicada la versió base de la plantilla multilingüe del projecte (ES/CA/EN) amb estructura...',
          description: "",
          section: "News",},{id: "outputs-open-geospatial-dataset",
          title: 'Open geospatial dataset',
          description: "Harmonized project dataset ready for reuse and citation.",
          section: "Outputs",handler: () => {
              window.location.href = "/unaltraweb/outputs/1_open-dataset/";
            },},{id: "outputs-interactive-web-map",
          title: 'Interactive web map',
          description: "Browser-based map viewer for exploring project indicators.",
          section: "Outputs",handler: () => {
              window.location.href = "/unaltraweb/outputs/2_interactive-web-map/";
            },},{id: "outputs-methodological-guide",
          title: 'Methodological guide',
          description: "Reproducible workflow for data processing and analysis.",
          section: "Outputs",handler: () => {
              window.location.href = "/unaltraweb/outputs/3_methodological-guide/";
            },},{id: "outputs-policy-brief",
          title: 'Policy brief',
          description: "Action-oriented summary for decision makers and stakeholders.",
          section: "Outputs",handler: () => {
              window.location.href = "/unaltraweb/outputs/4_policy-brief/";
            },},{id: "outputs-territorial-resilience-indicator-social-dimension-communities",
          title: 'Territorial resilience indicator (social dimension: communities)',
          description: "Demo indicator card with methodological sheet, sample calculations, and interpretation thresholds.",
          section: "Outputs",handler: () => {
              window.location.href = "/unaltraweb/outputs/5_territorial-resilience-social-indicator/";
            },},{id: "outputs-conjunt-de-dades-geoespacials-obert",
          title: 'Conjunt de dades geoespacials obert',
          description: "Dataset harmonitzat del projecte llest per a reutilització i citació.",
          section: "Outputs",handler: () => {
              window.location.href = "/unaltraweb/ca/outputs/conjunt-dades-geoespacials/";
            },},{id: "outputs-mapa-web-interactiu",
          title: 'Mapa web interactiu',
          description: "Visor cartogràfic per explorar indicadors del projecte.",
          section: "Outputs",handler: () => {
              window.location.href = "/unaltraweb/ca/outputs/mapa-web-interactiu/";
            },},{id: "outputs-guia-metodològica",
          title: 'Guia metodològica',
          description: "Flux reproduïble per al processament i l&#39;anàlisi de dades.",
          section: "Outputs",handler: () => {
              window.location.href = "/unaltraweb/ca/outputs/guia-metodologica/";
            },},{id: "outputs-informe-de-recomanacions",
          title: 'Informe de recomanacions',
          description: "Resum accionable per a decisors i agents del territori.",
          section: "Outputs",handler: () => {
              window.location.href = "/unaltraweb/ca/outputs/informe-recomanacions/";
            },},{id: "outputs-indicador-de-resiliència-territorial-dimensió-social-comunitats",
          title: 'Indicador de resiliència territorial (dimensió social: comunitats)',
          description: "Fitxa demo amb metodologia, càlculs de mostra i llindars d&#39;interpretació.",
          section: "Outputs",handler: () => {
              window.location.href = "/unaltraweb/ca/outputs/indicador-resiliencia-territorial-social/";
            },},{id: "outputs-conjunto-de-datos-geoespaciales-abierto",
          title: 'Conjunto de datos geoespaciales abierto',
          description: "Dataset armonizado del proyecto listo para reutilización y cita.",
          section: "Outputs",handler: () => {
              window.location.href = "/unaltraweb/es/outputs/conjunto-datos-geoespaciales/";
            },},{id: "outputs-mapa-web-interactivo",
          title: 'Mapa web interactivo',
          description: "Visor cartográfico para explorar indicadores del proyecto.",
          section: "Outputs",handler: () => {
              window.location.href = "/unaltraweb/es/outputs/mapa-web-interactivo/";
            },},{id: "outputs-guía-metodológica",
          title: 'Guía metodológica',
          description: "Flujo reproducible para el procesamiento y análisis de datos.",
          section: "Outputs",handler: () => {
              window.location.href = "/unaltraweb/es/outputs/guia-metodologica/";
            },},{id: "outputs-informe-de-recomendaciones",
          title: 'Informe de recomendaciones',
          description: "Resumen accionable para decisores y agentes del territorio.",
          section: "Outputs",handler: () => {
              window.location.href = "/unaltraweb/es/outputs/informe-recomendaciones/";
            },},{id: "outputs-indicador-de-resiliencia-territorial-dimensión-social-comunidades",
          title: 'Indicador de resiliencia territorial (dimensión social: comunidades)',
          description: "Ficha demo con metodología, cálculos de ejemplo y umbrales de interpretación.",
          section: "Outputs",handler: () => {
              window.location.href = "/unaltraweb/es/outputs/indicador-resiliencia-territorial-social/";
            },},{id: "projects-project-1",
          title: 'project 1',
          description: "with background image",
          section: "Projects",handler: () => {
              window.location.href = "/unaltraweb/projects/1_project/";
            },},{id: "projects-project-2",
          title: 'project 2',
          description: "a project with a background image and giscus comments",
          section: "Projects",handler: () => {
              window.location.href = "/unaltraweb/projects/2_project/";
            },},{id: "projects-project-3-with-very-long-name",
          title: 'project 3 with very long name',
          description: "a project that redirects to another website",
          section: "Projects",handler: () => {
              window.location.href = "/unaltraweb/projects/3_project/";
            },},{id: "projects-project-4",
          title: 'project 4',
          description: "another without an image",
          section: "Projects",handler: () => {
              window.location.href = "/unaltraweb/projects/4_project/";
            },},{id: "projects-project-5",
          title: 'project 5',
          description: "a project with a background image",
          section: "Projects",handler: () => {
              window.location.href = "/unaltraweb/projects/5_project/";
            },},{id: "projects-project-6",
          title: 'project 6',
          description: "a project with no image",
          section: "Projects",handler: () => {
              window.location.href = "/unaltraweb/projects/6_project/";
            },},{id: "projects-project-7",
          title: 'project 7',
          description: "with background image",
          section: "Projects",handler: () => {
              window.location.href = "/unaltraweb/projects/7_project/";
            },},{id: "projects-project-8",
          title: 'project 8',
          description: "an other project with a background image and giscus comments",
          section: "Projects",handler: () => {
              window.location.href = "/unaltraweb/projects/8_project/";
            },},{id: "projects-project-9",
          title: 'project 9',
          description: "another project with an image 🎉",
          section: "Projects",handler: () => {
              window.location.href = "/unaltraweb/projects/9_project/";
            },},{id: "theses-001-example",
          title: '001 Example',
          description: "",
          section: "Theses",handler: () => {
              window.location.href = "/unaltraweb/theses/001-example/";
            },},{id: "theses-002-example",
          title: '002 Example',
          description: "",
          section: "Theses",handler: () => {
              window.location.href = "/unaltraweb/theses/002-example/";
            },},{id: "theses-003-example",
          title: '003 Example',
          description: "",
          section: "Theses",handler: () => {
              window.location.href = "/unaltraweb/theses/003-example/";
            },},{
        id: 'social-email',
        title: 'email',
        section: 'Socials',
        handler: () => {
          window.open("mailto:%79%6F%75@%65%78%61%6D%70%6C%65.%63%6F%6D", "_blank");
        },
      },{
        id: 'social-rss',
        title: 'RSS Feed',
        section: 'Socials',
        handler: () => {
          window.open("/unaltraweb/feed.xml", "_blank");
        },
      },{
        id: 'social-custom_social',
        title: 'Custom_social',
        section: 'Socials',
        handler: () => {
          window.open("https://www.alberteinstein.com/", "_blank");
        },
      },{
      id: 'light-theme',
      title: 'Change theme to light',
      description: 'Change the theme of the site to Light',
      section: 'Theme',
      handler: () => {
        setThemeSetting("light");
      },
    },
    {
      id: 'dark-theme',
      title: 'Change theme to dark',
      description: 'Change the theme of the site to Dark',
      section: 'Theme',
      handler: () => {
        setThemeSetting("dark");
      },
    },
    {
      id: 'system-theme',
      title: 'Use system default theme',
      description: 'Change the theme of the site to System Default',
      section: 'Theme',
      handler: () => {
        setThemeSetting("system");
      },
    },];
