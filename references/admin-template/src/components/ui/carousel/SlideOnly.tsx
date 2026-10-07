import { Autoplay } from "swiper/modules";
import { Swiper, SwiperSlide } from "swiper/react";

const carouselData = [
  {
    thumbnail: "/images/carousel/carousel-01.png",
  },
  {
    thumbnail: "/images/carousel/carousel-02.png",
  },
  {
    thumbnail: "/images/carousel/carousel-03.png",
  },
  {
    thumbnail: "/images/carousel/carousel-04.png",
  },
];

export default function SlideOnly() {
  const swiperOptions = {
    modules: [Autoplay],
    autoplay: {
      delay: 5000,
      disableOnInteraction: false,
    },
  };

  return (
    <div className="carouselOne rounded-lg border border-gray-200 dark:border-gray-800">
      <Swiper {...swiperOptions}>
        {carouselData.map((item, i) => (
          <SwiperSlide key={i + 1}>
            <div className="overflow-hidden rounded-lg">
              <img
                src={item.thumbnail}
                className="h-74.25 w-full rounded-lg"
                alt="carousel"
              />
            </div>
          </SwiperSlide>
        ))}
      </Swiper>
    </div>
  );
}
