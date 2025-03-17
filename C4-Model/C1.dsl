workspace {
    model {
        user = person "User" "Interacts with the system via UI"

        mailIndexer = softwareSystem "Mail Indexer" "" {
            ui = container "UI" "User Interface"
            collector = container "Collector" "Gathers data from various sources"
            cleaner = container "Cleaner" "Processes and cleans data"
            index = container "Index" "Indexes the cleaned data"
            search = container "Search" "Handles search queries"
            mariadb = container "MariaDB" "Stores processed data"
        }

        user -> ui "Interacts with"
        ui -> collector "Sends requests to"
        ui -> search "Request data from"
        search -> mariadb "Fetches data from"
        collector -> cleaner "Sends data for processing"
        cleaner -> index "Cleans and passes to index"
        index -> mariadb "Indexes data in"
    }

    views {
        systemContext mailIndexer {
            include *
            autolayout lr
        }

        container mailIndexer {
            include *
            autolayout lr
        }
    }
}