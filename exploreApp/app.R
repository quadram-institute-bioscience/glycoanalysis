library(shiny)
library(bslib)
library(dplyr)
library(tidyr)
library(ggplot2)
library(DT)
library(plotly)
library(readr)

# Define UI
ui <- page_sidebar(
  title = "Glycan Analysis",
  sidebar = sidebar(
    fileInput("file", "Upload Glycoprep Output (.tsv)", accept = ".tsv"),
    numericInput("confidence_threshold", "Confidence Threshold", value = 0.9, min = 0, max = 1, step = 0.05),
    selectInput("group_by", "Group By", choices = c("condition", "severity", "sex", "age_group"), selected = "condition"),
    actionButton("reset", "Reset Filters")
  ),
  navset_card_underline(
    nav_panel("Data Explorer", 
              DTOutput("raw_table")
    ),
    nav_panel("Composition",
              card(
                card_header("Glycan Features Composition"),
                layout_columns(
                  plotlyOutput("sialylation_plot"),
                  plotlyOutput("fucosylation_plot"),
                  plotlyOutput("sulfation_plot")
                )
              )
    ),
    nav_panel("Prevalence",
              plotlyOutput("prevalence_plot")
    )
  )
)

# Define Server
server <- function(input, output, session) {
  
  options(shiny.maxRequestSize = 30*1024^2) # Increase upload size limit to 30MB
  
  # Reactive Data Loader
  data <- reactive({
    req(input$file)
    df <- read_tsv(input$file$datapath, show_col_types = FALSE)
    
    # Basic cleaning/type conversion if needed
    if("confidence" %in% names(df)){
      df <- df %>% filter(confidence >= input$confidence_threshold)
    }
    
    return(df)
  })
  
  # Data Table
  output$raw_table <- renderDT({
    req(data())
    datatable(data(), options = list(scrollX = TRUE, pageLength = 10))
  })
  
  # Helper forComposition Plots
  plot_composition <- function(df, feature_col, group_col) {
    # Ensure feature column exists and is strictly Yes/No or similar
    # We assume 'Yes' indicates presence
    
    if(!feature_col %in% names(df) || !group_col %in% names(df)) return(NULL)
    
    summary_df <- df %>%
      group_by(sample_sheet, !!sym(group_col)) %>%
      summarise(
        Total_Intens = sum(intens, na.rm = TRUE),
        Feature_Intens = sum(intens[!!sym(feature_col) == "Yes"], na.rm = TRUE),
        .groups = "drop"
      ) %>%
      mutate(Percentage = (Feature_Intens / Total_Intens) * 100)
    
    p <- ggplot(summary_df, aes(x = !!sym(group_col), y = Percentage, fill = !!sym(group_col))) +
      geom_boxplot(alpha = 0.7) +
      geom_jitter(width = 0.2, alpha = 0.5) +
      theme_minimal() +
      labs(y = paste("%", feature_col), title = paste(feature_col, "by", group_col)) +
      theme(legend.position = "none")
    
    return(ggplotly(p))
  }
  
  output$sialylation_plot <- renderPlotly({
    req(data())
    plot_composition(data(), "Sialylation", input$group_by)
  })
  
  output$fucosylation_plot <- renderPlotly({
    req(data())
    plot_composition(data(), "Fucosylation", input$group_by)
  })
  
  output$sulfation_plot <- renderPlotly({
    req(data())
    plot_composition(data(), "Sulfation", input$group_by)
  })
  
  # Prevalence Plot
  output$prevalence_plot <- renderPlotly({
    req(data())
    
    # Calculate prevalence: % of samples that have this glycan (Composition)
    total_samples <- n_distinct(data()$sample_sheet)
    
    prev_df <- data() %>%
      group_by(Composition) %>%
      summarise(
        Count = n_distinct(sample_sheet),
        Prevalence = (Count / total_samples) * 100,
        Avg_Intens = mean(intens, na.rm=TRUE),
        .groups = "drop"
      ) %>%
      arrange(desc(Prevalence)) %>%
      head(20) # Top 20 for readability
    
    p <- ggplot(prev_df, aes(x = reorder(Composition, Prevalence), y = Prevalence, text = paste("Avg Intensity:", round(Avg_Intens)))) +
      geom_bar(stat = "identity", fill = "steelblue") +
      coord_flip() +
      theme_minimal() +
      labs(x = "Glycan Composition", y = "Prevalence (% of Samples)", title = "Top 20 Most Prevalent Glycans")
    
    ggplotly(p, tooltip = c("y", "text"))
  })
}

shinyApp(ui, server)
