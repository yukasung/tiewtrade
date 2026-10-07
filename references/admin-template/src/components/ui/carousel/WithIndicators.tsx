import { Autoplay, Pagination } from "swiper/modules";
import { Swiper, SwiperSlide } from "swiper/react";

const carouselData = [
  {
    thumbnail: "/images/carousel/carousel-01.png",
  },
  {
    thumbnail: "/images/carousel/carousel-03.png",
  },
  {
    thumbnail: "/images/carousel/carousel-02.png",
  },
  {
    thumbnail: "/images/carousel/carousel-04.png",
  },
];

export default function WithIndicators() {
  const swiperOptions = {
    modules: [Pagination, Autoplay],
    autoplay: {
      delay: 5000,
      disableOnInteraction: false,
    },
    pagination: {
      el: ".swiper-pagination",
      clickable: true,
    },
  };

  return (
    <div className="carouselThree relative rounded-lg border border-gray-200 dark:border-gray-800">
      <Swiper {...swiperOptions}>
        {/* <!-- slider item --> */}
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
        {/* <!-- If we need pagination --> */}
        <div className="swiper-pagination"></div>
      </Swiper>
    </div>
  );
}
