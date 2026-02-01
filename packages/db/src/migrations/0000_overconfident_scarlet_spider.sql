CREATE TABLE "advertisements" (
	"id" serial PRIMARY KEY NOT NULL,
	"restaurant_id" integer NOT NULL,
	"ad_type" varchar(50) NOT NULL,
	"title" varchar(255),
	"content" text,
	"image_url" varchar(500),
	"target_url" varchar(500),
	"start_date" date,
	"end_date" date,
	"is_active" boolean DEFAULT false NOT NULL,
	"impressions" integer DEFAULT 0 NOT NULL,
	"clicks" integer DEFAULT 0 NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "dishes" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" varchar(255) NOT NULL,
	"slug" varchar(255) NOT NULL,
	"canonical_name" varchar(255),
	"category" varchar(50),
	"subcategory" varchar(100),
	"is_main_dish" boolean DEFAULT true NOT NULL,
	"aliases" text[],
	"search_vector" "tsvector",
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "dishes_slug_unique" UNIQUE("slug")
);
--> statement-breakpoint
CREATE TABLE "restaurant_dishes" (
	"id" serial PRIMARY KEY NOT NULL,
	"restaurant_id" integer NOT NULL,
	"dish_id" integer NOT NULL,
	"avg_sentiment" numeric(3, 2),
	"positive_count" integer DEFAULT 0 NOT NULL,
	"negative_count" integer DEFAULT 0 NOT NULL,
	"neutral_count" integer DEFAULT 0 NOT NULL,
	"total_mentions" integer DEFAULT 0 NOT NULL,
	"computed_score" numeric(3, 2),
	"price" numeric(8, 2),
	"last_updated" timestamp with time zone
);
--> statement-breakpoint
CREATE TABLE "restaurant_platforms" (
	"id" serial PRIMARY KEY NOT NULL,
	"restaurant_id" integer NOT NULL,
	"platform" varchar(50) NOT NULL,
	"external_id" varchar(255) NOT NULL,
	"external_url" varchar(1000),
	"platform_score" numeric(3, 2),
	"platform_reviews" integer DEFAULT 0 NOT NULL,
	"match_confidence" numeric(3, 2),
	"last_scraped" timestamp with time zone,
	"raw_data" jsonb
);
--> statement-breakpoint
CREATE TABLE "restaurants" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" varchar(255) NOT NULL,
	"slug" varchar(255) NOT NULL,
	"address" text,
	"district" varchar(100),
	"neighborhood" varchar(100),
	"location" geography(POINT, 4326),
	"phone" varchar(20),
	"website" varchar(500),
	"cuisine_type" text[],
	"price_range" smallint,
	"overall_score" numeric(3, 2),
	"total_reviews" integer DEFAULT 0 NOT NULL,
	"is_active" boolean DEFAULT true NOT NULL,
	"image_url" varchar(500),
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "restaurants_slug_unique" UNIQUE("slug")
);
--> statement-breakpoint
CREATE TABLE "review_dish_mentions" (
	"id" serial PRIMARY KEY NOT NULL,
	"review_id" integer NOT NULL,
	"dish_id" integer NOT NULL,
	"mention_text" text,
	"sentiment" varchar(10),
	"sentiment_score" numeric(4, 3),
	"extraction_method" varchar(20),
	"confidence" numeric(3, 2),
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "reviews" (
	"id" serial PRIMARY KEY NOT NULL,
	"restaurant_platform_id" integer NOT NULL,
	"external_review_id" varchar(255),
	"author_name" varchar(255),
	"rating" smallint,
	"text" text NOT NULL,
	"review_date" timestamp with time zone,
	"language" varchar(10) DEFAULT 'tr' NOT NULL,
	"scraped_at" timestamp with time zone DEFAULT now() NOT NULL,
	"processed" boolean DEFAULT false NOT NULL
);
--> statement-breakpoint
CREATE TABLE "scrape_jobs" (
	"id" serial PRIMARY KEY NOT NULL,
	"platform" varchar(50) NOT NULL,
	"target_type" varchar(50) NOT NULL,
	"target_id" varchar(255),
	"status" varchar(20) DEFAULT 'pending' NOT NULL,
	"started_at" timestamp with time zone,
	"completed_at" timestamp with time zone,
	"items_scraped" integer DEFAULT 0 NOT NULL,
	"error_message" text,
	"metadata" jsonb
);
--> statement-breakpoint
ALTER TABLE "advertisements" ADD CONSTRAINT "advertisements_restaurant_id_restaurants_id_fk" FOREIGN KEY ("restaurant_id") REFERENCES "public"."restaurants"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "restaurant_dishes" ADD CONSTRAINT "restaurant_dishes_restaurant_id_restaurants_id_fk" FOREIGN KEY ("restaurant_id") REFERENCES "public"."restaurants"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "restaurant_dishes" ADD CONSTRAINT "restaurant_dishes_dish_id_dishes_id_fk" FOREIGN KEY ("dish_id") REFERENCES "public"."dishes"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "restaurant_platforms" ADD CONSTRAINT "restaurant_platforms_restaurant_id_restaurants_id_fk" FOREIGN KEY ("restaurant_id") REFERENCES "public"."restaurants"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "review_dish_mentions" ADD CONSTRAINT "review_dish_mentions_review_id_reviews_id_fk" FOREIGN KEY ("review_id") REFERENCES "public"."reviews"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "review_dish_mentions" ADD CONSTRAINT "review_dish_mentions_dish_id_dishes_id_fk" FOREIGN KEY ("dish_id") REFERENCES "public"."dishes"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "reviews" ADD CONSTRAINT "reviews_restaurant_platform_id_restaurant_platforms_id_fk" FOREIGN KEY ("restaurant_platform_id") REFERENCES "public"."restaurant_platforms"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "idx_advertisements_restaurant_id" ON "advertisements" USING btree ("restaurant_id");--> statement-breakpoint
CREATE INDEX "idx_advertisements_active" ON "advertisements" USING btree ("is_active") WHERE "advertisements"."is_active" = true;--> statement-breakpoint
CREATE INDEX "idx_dishes_search_vector" ON "dishes" USING gin ("search_vector");--> statement-breakpoint
CREATE INDEX "idx_dishes_canonical_name_trgm" ON "dishes" USING gin ("canonical_name" gin_trgm_ops);--> statement-breakpoint
CREATE UNIQUE INDEX "idx_restaurant_dishes_unique" ON "restaurant_dishes" USING btree ("restaurant_id","dish_id");--> statement-breakpoint
CREATE INDEX "idx_restaurant_dishes_restaurant_id_dish_id" ON "restaurant_dishes" USING btree ("restaurant_id","dish_id");--> statement-breakpoint
CREATE UNIQUE INDEX "idx_restaurant_platforms_unique" ON "restaurant_platforms" USING btree ("platform","external_id");--> statement-breakpoint
CREATE INDEX "idx_restaurant_platforms_restaurant_id" ON "restaurant_platforms" USING btree ("restaurant_id");--> statement-breakpoint
CREATE INDEX "idx_restaurants_fts" ON "restaurants" USING gin (to_tsvector('turkish', coalesce("name", '') || ' ' || coalesce("address", '')));--> statement-breakpoint
CREATE INDEX "idx_restaurants_name_trgm" ON "restaurants" USING gin ("name" gin_trgm_ops);--> statement-breakpoint
CREATE INDEX "idx_restaurants_location" ON "restaurants" USING gist ("location");--> statement-breakpoint
CREATE INDEX "idx_review_dish_mentions_review_id" ON "review_dish_mentions" USING btree ("review_id");--> statement-breakpoint
CREATE INDEX "idx_review_dish_mentions_dish_id" ON "review_dish_mentions" USING btree ("dish_id");--> statement-breakpoint
CREATE UNIQUE INDEX "idx_reviews_unique" ON "reviews" USING btree ("restaurant_platform_id","external_review_id");--> statement-breakpoint
CREATE INDEX "idx_reviews_restaurant_platform_id" ON "reviews" USING btree ("restaurant_platform_id");--> statement-breakpoint
CREATE INDEX "idx_reviews_unprocessed" ON "reviews" USING btree ("processed") WHERE NOT "reviews"."processed";--> statement-breakpoint
CREATE INDEX "idx_scrape_jobs_status" ON "scrape_jobs" USING btree ("status");--> statement-breakpoint
CREATE INDEX "idx_scrape_jobs_platform" ON "scrape_jobs" USING btree ("platform");