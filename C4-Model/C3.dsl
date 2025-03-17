**//Search Container
workspace {
    model {

        Container = softwareSystem "Search Container" "" {
            
            SearchContainer = container "Main" "Takes HTTP request from UI and fetches data from DB"
        }
    }

    views {
        systemContext container {
            include *
            autolayout lr
        }

        container Container {
            include *
            autolayout lr
        }
    }
}
**// Search Container

**// Index Container
workspace {
    model {

        Container = softwareSystem "Index Container" "" {

            indexContainer = container "Main" "Gets the cleaned data through RabbitMQ, then passes it to the DB"
        }
    }

    views {
        systemContext container {
            include *
            autolayout lr
        }

        container Container {
            include *
            autolayout lr
        }
    }
}
**// Index Container

**// Cleaner Container
workspace {
    model {

        Container = softwareSystem "Cleaner Container" "" {

            CleanerContainer = container "Main" "Gets the data through RabbitMQ, processes it and then passes it through RabbitMQ"
        }
    }

    views {
        systemContext container {
            include *
            autolayout lr
        }

        container Container {
            include *
            autolayout lr
        }
    }
}
**// Cleaner Container
